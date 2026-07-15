"""Keepa API wrapper — discovery + per-ASIN data pull."""
import logging
from typing import Optional
import keepa

from . import config
from . import alerts
from .models import AsinRecord

log = logging.getLogger(__name__)


def _api() -> keepa.Keepa:
    return keepa.Keepa(config.KEEPA_API_KEY)


def discover_asins() -> list[str]:
    """
    Query Keepa Product Finder across multiple wholesale-friendly categories.
    Each run sweeps all target categories (1 page each) for diverse brand coverage.
    Returns deduped list of ASIN strings, capped to avoid token overuse.
    """
    api = _api()

    # Wholesale-friendly categories — actively targeted (not just exclusions)
    TARGET_CATEGORIES = [
        1055398,     # Home & Kitchen
        3375251,     # Sports & Outdoors
        228013,      # Tools & Home Improvement
        2619533,     # Pet Supplies
        3760901,     # Health & Household
        11055981,    # Beauty & Personal Care
        1064954,     # Office Products
        2972638011,  # Patio, Lawn & Garden
        15684181,    # Automotive
        165796011,   # Baby
        165793011,   # Toys & Games
        16310101,    # Grocery & Gourmet Food (snacks, supplements, packaged goods)
    ]

    base_params = {
        "perPage": 500,
        "sort": [["current_SALES", "desc"]],
        "avg30_COUNT_NEW_gte": config.MIN_SELLERS,
        "avg30_COUNT_NEW_lte": config.MAX_SELLERS,
        "current_NEW_gte": int(config.MIN_PRICE_USD * 100),
        "avg30_SALES_gte": config.MIN_UNITS_PER_MONTH,
        "current_SALES_lte": 70000,
        "current_COUNT_REVIEWS_gte": 50,
    }

    all_asins: list[str] = []
    seen: set[str] = set()

    for cat_id in TARGET_CATEGORIES:
        params = {**base_params, "categories_include": [cat_id], "page": 0}
        try:
            result = api.product_finder(params)
            new = [a for a in (result or []) if a not in seen]
            seen.update(new)
            all_asins.extend(new)
            log.info("Category %s: %d new ASINs (total %d)", cat_id, len(new), len(all_asins))
        except Exception as exc:
            log.error("Keepa Product Finder category %s failed: %s", cat_id, exc)
            if _is_token_exhaustion(exc):
                alerts.alert_keepa_exhausted(exc)
                break

    # Cap total to control token spend on detail fetches (~2 tokens/ASIN)
    MAX_FETCH = 600
    if len(all_asins) > MAX_FETCH:
        all_asins = all_asins[:MAX_FETCH]
        log.info("Capped ASIN pool to %d for token budget", MAX_FETCH)

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
            products = api.query(chunk, stats=180, history=False)
        except Exception as exc:
            log.warning("Keepa query failed for chunk %s: %s", chunk, exc)
            if _is_token_exhaustion(exc):
                alerts.alert_keepa_exhausted(exc)
                break   # no point continuing if tokens are gone
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

        # Monthly units: keepa monthlySold field; fall back to pre-filter floor if missing
        units_per_month = int(p.get("monthlySold") or 0) or config.MIN_UNITS_PER_MONTH

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
    """
    Estimate Amazon's presence using stats (works with history=False).
    stats.current[0] and stats.avg30[0] = Amazon price at index 0; -1 = not present.
    Returns a synthetic percentage: 90 if currently present, 50 if present in avg30, else 0.
    """
    try:
        stats = p.get("stats") or {}
        current = stats.get("current") or []
        avg30 = stats.get("avg30") or []

        def _amazon_active(arr):
            try:
                v = arr[0]
                return isinstance(v, (int, float)) and v > 0
            except (IndexError, TypeError):
                return False

        if _amazon_active(current):
            return 90.0   # Amazon actively selling right now
        if _amazon_active(avg30):
            return 50.0   # Amazon was selling in the past 30 days
        return 0.0
    except Exception:
        return 0.0


def _price_90d_ago(p: dict) -> float:
    """Return the new-listing price from stats.avg90 (index 1 = NEW price)."""
    try:
        stats = p.get("stats") or {}
        avg90 = stats.get("avg90") or []
        try:
            v = avg90[1]
            return v / 100.0 if isinstance(v, (int, float)) and v > 0 else 0.0
        except (IndexError, TypeError):
            return 0.0
    except Exception:
        return 0.0


def _is_token_exhaustion(exc: Exception) -> bool:
    """Keepa raises errors with messages like 'not enough tokens' or status 429."""
    msg = str(exc).lower()
    return any(phrase in msg for phrase in ["token", "429", "rate limit", "quota", "exceeded"])
