"""Keepa API wrapper — discovery + per-ASIN data pull."""
import time
import logging
from typing import Optional
import keepa

from . import config
from . import alerts
from .models import AsinRecord

log = logging.getLogger(__name__)


def _api() -> keepa.Keepa:
    return keepa.Keepa(config.KEEPA_API_KEY)


def discover_asins(pages: int = 3) -> list[str]:
    """
    Run Keepa Product Finder across multiple pages to maximise ASIN coverage.
    500 ASINs per page, deduped. Returns list of ASIN strings.
    """
    api = _api()
    base_params = {
        "perPage": 500,
        "sort": [["current_SALES", "desc"]],
        "avg30_COUNT_NEW_gte": config.MIN_SELLERS,
        "avg30_COUNT_NEW_lte": config.MAX_SELLERS,
        "current_NEW_gte": int(config.MIN_PRICE_USD * 100),
        "avg30_SALES_gte": config.MIN_UNITS_PER_MONTH,
    }
    all_asins: list[str] = []
    seen: set[str] = set()
    for page in range(pages):
        params = {**base_params, "page": page}
        try:
            result = api.product_finder(params)
            new = [a for a in (result or []) if a not in seen]
            seen.update(new)
            all_asins.extend(new)
            log.info("Product Finder page %d: %d ASINs (total %d)", page, len(new), len(all_asins))
            if len(result or []) < 500:
                break  # no more pages
        except Exception as exc:
            log.error("Keepa Product Finder page %d failed: %s", page, exc)
            if _is_token_exhaustion(exc):
                alerts.alert_keepa_exhausted(exc)
            break
    return all_asins


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

    return records


def _parse_product(p: dict) -> Optional[AsinRecord]:
    try:
        asin = p.get("asin", "")
        brand = (p.get("brand") or "").strip()
        title = (p.get("title") or "").strip()
        category = (p.get("categoryTree") or [{}])[-1].get("name", "")

        stats = p.get("stats") or {}
        current = stats.get("current") or []
        avg30 = stats.get("avg30") or []

        # Price: Keepa csv index 1 = NEW price, stored in cents; -1 = not available
        def _cents(arr, idx):
            try:
                v = arr[idx]
                return v / 100.0 if v and v > 0 else 0.0
            except (IndexError, TypeError):
                return 0.0

        price_usd = _cents(current, 1) or _cents(avg30, 1)

        # COUNT_NEW = csv index 10 — number of active new 3P sellers
        def _int_stat(arr, idx):
            try:
                v = arr[idx]
                return int(v) if v and v > 0 else 0
            except (IndexError, TypeError):
                return 0

        active_sellers = _int_stat(current, 10) or _int_stat(avg30, 10)

        # Monthly units: keepa monthlySold field (populated for many products)
        units_per_month = int(p.get("monthlySold") or 0)

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


def _is_token_exhaustion(exc: Exception) -> bool:
    """Keepa raises errors with messages like 'not enough tokens' or status 429."""
    msg = str(exc).lower()
    return any(phrase in msg for phrase in ["token", "429", "rate limit", "quota", "exceeded"])
