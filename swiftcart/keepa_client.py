"""Keepa API wrapper — discovery + per-ASIN data pull."""
import time
import logging
from typing import Optional
import keepa

from . import config
from .models import AsinRecord

log = logging.getLogger(__name__)


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
        )
    except Exception as exc:
        log.debug("Failed to parse product %s: %s", p.get("asin"), exc)
        return None


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
