"""Keepa API wrapper — discovery + per-ASIN data pull."""
import time
import logging
from typing import Optional
import keepa

from . import config
from . import alerts
from .models import AsinRecord

log = logging.getLogger(__name__)

AMAZON_SELLER_ID = "ATVPDKIKX0DER"   # Amazon's own seller ID on amazon.com


def _api() -> keepa.Keepa:
    return keepa.Keepa(config.KEEPA_API_KEY)


def discover_asins(limit: int = 500) -> list[dict]:
    """
    Run Keepa Product Finder with the project's ASIN-level filters.
    Returns raw product dicts (cheap — no token burn per product here).
    """
    api = _api()
    params = {
        "page": 0,
        "perPage": min(limit, 500),
        "sort": [["monthlySold", "desc"]],
        "selection": {
            "sellerCount_gte": config.MIN_SELLERS,
            "sellerCount_lte": config.MAX_SELLERS,
            "current_AMAZON_gte": -1,     # present = -1 means "not present"
            "current_price_gte": int(config.MIN_PRICE_USD * 100),
            "monthlySold_gte": config.MIN_UNITS_PER_MONTH,
        },
    }
    try:
        result = api.product_finder(params)
        log.info("Product Finder returned %d ASINs", len(result))
        return result or []
    except Exception as exc:
        log.error("Keepa Product Finder failed: %s", exc)
        if _is_token_exhaustion(exc):
            alerts.alert_keepa_exhausted(exc)
        return []


def fetch_asin_details(asins: list[str]) -> list[AsinRecord]:
    """
    Pull full product + offer data for a batch of ASINs.
    Paced at 1 token/minute as configured.
    """
    api = _api()
    records: list[AsinRecord] = []
    batch_size = 10

    for i in range(0, len(asins), batch_size):
        chunk = asins[i: i + batch_size]
        try:
            products = api.query(chunk, stats=90, offers=20, history=True)
        except Exception as exc:
            log.warning("Keepa query failed for chunk %s: %s", chunk, exc)
            if _is_token_exhaustion(exc):
                alerts.alert_keepa_exhausted(exc)
                break   # no point continuing if tokens are gone
            time.sleep(config.KEEPA_TOKEN_PAUSE_SECONDS)
            continue

        for p in products:
            rec = _parse_product(p)
            if rec:
                records.append(rec)

        log.info("Fetched %d/%d ASINs", min(i + batch_size, len(asins)), len(asins))
        time.sleep(config.KEEPA_TOKEN_PAUSE_SECONDS)

    return records


def _parse_product(p: dict) -> Optional[AsinRecord]:
    try:
        asin = p.get("asin", "")
        brand = (p.get("brand") or "").strip()
        title = (p.get("title") or "").strip()
        category = (p.get("categoryTree") or [{}])[-1].get("name", "")

        # Price: Keepa stores in cents; -1 means not available
        price_cents = p.get("stats", {}).get("current", [None] * 2)
        price_usd = (price_cents[1] / 100.0) if (price_cents and price_cents[1] and price_cents[1] > 0) else 0.0

        units_per_month = p.get("monthlySold") or 0

        # Seller count from offers
        offers = p.get("offers") or []
        active_sellers = len([o for o in offers if o.get("isFBA") or o.get("isMerchant")])

        # Amazon present %: amazonExcluded flag; alternatively check csv data
        amazon_pct = _calc_amazon_presence(p)

        # 90-day price for crash detection
        price_90d = _price_90d_ago(p)

        weight_lb = _parse_weight(p)
        fba_fee_usd = _parse_fba_fee(p)
        bsr = _parse_bsr(p)
        amazon_is_buybox = _parse_amazon_buybox(p)

        if not asin or not brand:
            return None

        return AsinRecord(
            asin=asin,
            brand=brand,
            title=title,
            price_usd=price_usd,
            units_per_month=int(units_per_month),
            seller_count=active_sellers,
            amazon_present_pct=amazon_pct,
            price_90d_ago=price_90d,
            category=category,
            weight_lb=weight_lb,
            fba_fee_usd=fba_fee_usd,
            bsr=bsr,
            amazon_is_buybox=amazon_is_buybox,
        )
    except Exception as exc:
        log.debug("Failed to parse product %s: %s", p.get("asin"), exc)
        return None


def _parse_weight(p: dict) -> float:
    """Package weight in pounds — Keepa reports grams."""
    grams = p.get("packageWeight") or p.get("itemWeight") or 0
    try:
        return round(float(grams) / 453.592, 2) if grams else 0.0
    except Exception:
        return 0.0


def _parse_fba_fee(p: dict) -> float:
    """FBA pick-and-pack fee in USD — Keepa reports cents, 0 if not available."""
    cents = (p.get("fbaFees") or {}).get("pickAndPackFee")
    try:
        return round(cents / 100.0, 2) if cents else 0.0
    except Exception:
        return 0.0


def fetch_asin_details_by_upc(upcs: list[str]) -> dict[str, AsinRecord]:
    """
    Look up ASIN + product data by UPC/EAN in one pass, sized for invoice
    scans of hundreds to thousands of SKUs.

    Batches at Keepa's real per-request ceiling (100 codes) instead of the
    10 used for daily brand discovery. Pacing is driven by the account's
    actual `tokens_left` / `time_to_refill` rather than a fixed sleep, and
    a `KEEPA_TOKEN_RESERVE` buffer is left untouched so a large scan can't
    starve the daily brand-discovery run of tokens. `history`/`offers` are
    skipped (the most expensive, unbounded-cost part of a Keepa request);
    `buybox` is kept on since it's a fixed +2 tokens/product and is needed
    to tell whether Amazon itself currently holds the buy box.
    """
    api = _api()
    mapping: dict[str, AsinRecord] = {}
    batch_size = config.KEEPA_INVOICE_BATCH_SIZE

    for i in range(0, len(upcs), batch_size):
        chunk = upcs[i: i + batch_size]

        api.update_status()
        if api.tokens_left - len(chunk) < config.KEEPA_TOKEN_RESERVE:
            wait_s = api.time_to_refill
            log.info(
                "Pausing %.0fs to keep %d tokens in reserve for other Keepa jobs",
                wait_s, config.KEEPA_TOKEN_RESERVE,
            )
            time.sleep(wait_s)

        try:
            products = api.query(
                chunk, product_code_is_asin=False, stats=90, history=False, offers=None,
                buybox=True, wait=True,
            )
        except Exception as exc:
            log.warning("UPC lookup failed for chunk starting at %d: %s", i, exc)
            if _is_token_exhaustion(exc):
                alerts.alert_keepa_exhausted(exc)
                break
            continue

        for p in products:
            rec = _parse_product(p)
            if not rec:
                continue
            codes = set((p.get("upcList") or []) + (p.get("eanList") or []))
            matched_upc = next((u for u in chunk if u in codes), None)
            if matched_upc:
                mapping[matched_upc] = rec

        log.info("UPC lookup: %d/%d codes processed", min(i + batch_size, len(upcs)), len(upcs))

    return mapping


def _calc_amazon_presence(p: dict) -> float:
    """Estimate % of time Amazon held the Buy Box from csv[0] history."""
    try:
        csv = p.get("csv") or []
        # csv[0] = Amazon price history; -1 entries = not present
        amazon_history = csv[0] if csv else []
        # Values alternate: [timestamp, price, timestamp, price, ...]
        prices = amazon_history[1::2] if amazon_history else []
        if not prices:
            return 0.0
        present = sum(1 for v in prices if v and v > 0)
        return round(present / len(prices) * 100, 1)
    except Exception:
        return 0.0


def _price_90d_ago(p: dict) -> float:
    """Return the new-listing price approximately 90 days ago."""
    try:
        csv = p.get("csv") or []
        # csv[1] = new price history
        new_history = csv[1] if len(csv) > 1 else []
        prices = new_history[1::2] if new_history else []
        valid = [v / 100.0 for v in prices if v and v > 0]
        return valid[0] if valid else 0.0
    except Exception:
        return 0.0


def _parse_bsr(p: dict) -> int:
    """Current Best Sellers Rank — Keepa csv/stats type index 3 (SALES)."""
    try:
        current = (p.get("stats") or {}).get("current") or []
        rank = current[3] if len(current) > 3 else None
        return int(rank) if rank and rank > 0 else 0
    except Exception:
        return 0


def _parse_amazon_buybox(p: dict) -> bool:
    """True if Amazon's own seller ID currently holds the buy box."""
    try:
        stats = p.get("stats") or {}
        seller_id = stats.get("buyBoxSellerId") or p.get("buyBoxSellerId")
        return seller_id == AMAZON_SELLER_ID
    except Exception:
        return False


def _is_token_exhaustion(exc: Exception) -> bool:
    """Keepa raises errors with messages like 'not enough tokens' or status 429."""
    msg = str(exc).lower()
    return any(phrase in msg for phrase in ["token", "429", "rate limit", "quota", "exceeded"])
