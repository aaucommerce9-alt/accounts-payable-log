"""ASIN-level and brand-level filtering + scoring."""
import logging
from collections import defaultdict

from . import config
from .models import AsinRecord, BrandRecord

log = logging.getLogger(__name__)


AMAZON_OWN_BRANDS = {
    "amazonbasics", "amazon basics", "amazon essentials", "amazon collection",
    "amazon brand", "solimo", "pinzon", "goodthreads", "daily ritual",
    "core 10", "buttoned down", "206 collective", "ella moon", "lark & ro",
    "find.", "truth & fable", "iris & lilly", "coastal blue", "spotted zebra",
    "amazon aware", "presto!", "mama bear", "happy belly", "wickedly prime",
    "whole foods", "365 by whole foods", "fire tv", "kindle", "echo",
    "ring", "blink", "eero",
}

# Fortune 500 / household-name brands that will never wholesale to a small distributor
MEGA_BRANDS = {
    "samsung", "apple", "sony", "lg", "panasonic", "philips", "bosch", "siemens",
    "nike", "adidas", "under armour", "puma", "reebok", "new balance", "asics",
    "fossil", "casio", "seiko", "timex", "michael kors", "kate spade", "coach",
    "levi's", "levis", "gap", "h&m", "zara", "calvin klein", "tommy hilfiger",
    "ralph lauren", "polo ralph lauren", "lacoste", "gucci", "prada", "louis vuitton",
    "dyson", "shark", "bissell", "roomba", "irobot", "kitchenaid", "cuisinart",
    "instant pot", "ninja", "breville", "keurig", "nespresso", "hamilton beach",
    "lego", "hasbro", "mattel", "fisher-price", "fisher price", "barbie",
    "microsoft", "dell", "hp", "lenovo", "asus", "acer", "logitech", "razer",
    "bose", "jbl", "harman kardon", "sennheiser", "beats", "jabra",
    "coleman", "stanley", "yeti", "thermos", "hydro flask",
    "rubbermaid", "tupperware", "oxo", "black+decker", "black and decker",
    "dewalt", "milwaukee", "makita", "ryobi", "craftsman",
    "revlon", "l'oreal", "loreal", "maybelline", "neutrogena", "olay", "dove",
    "gillette", "oral-b", "colgate", "crest", "listerine",
    "johnson & johnson", "johnson and johnson", "band-aid", "tylenol", "advil",
    "purina", "hills science diet", "royal canin", "pedigree", "iams",
    "procter & gamble", "unilever", "3m", "scotch", "post-it",
}


def filter_asins(records: list[AsinRecord]) -> list[AsinRecord]:
    kept = []
    drop_reasons: dict[str, int] = {}
    for r in records:
        reasons = []
        if r.brand.lower() in AMAZON_OWN_BRANDS:
            reasons.append("amazon_brand")
        if r.brand.lower() in MEGA_BRANDS:
            reasons.append("mega_brand")
        if r.amazon_present_pct >= config.MAX_AMAZON_PRESENT_PCT:
            reasons.append(f"amazon_pct={r.amazon_present_pct}")
        if r.price_usd < config.MIN_PRICE_USD:
            reasons.append(f"price={r.price_usd}")
        # units_per_month already pre-filtered by Keepa product_finder (avg30_SALES_gte)
        # Only drop if we have a non-zero reading that's clearly too low
        if r.units_per_month > 0 and r.units_per_month < config.MIN_UNITS_PER_MONTH:
            reasons.append(f"units={r.units_per_month}")
        if _is_price_crash(r):
            reasons.append("price_crash")

        if reasons:
            log.debug("Drop ASIN %s (%s): %s", r.asin, r.brand, ", ".join(reasons))
            for reason in reasons:
                key = reason.split("=")[0]
                drop_reasons[key] = drop_reasons.get(key, 0) + 1
        else:
            kept.append(r)

    log.info("ASIN filter: %d → %d | drop breakdown: %s", len(records), len(kept), drop_reasons)
    # Log sample values to diagnose parsing issues
    if records and not kept:
        sample = records[:3]
        for s in sample:
            log.info("Sample ASIN %s: price=%.2f sellers=%d units=%d amazon_pct=%.1f",
                     s.asin, s.price_usd, s.seller_count, s.units_per_month, s.amazon_present_pct)
    return kept


def _is_price_crash(r: AsinRecord) -> bool:
    if r.price_90d_ago <= 0 or r.price_usd <= 0:
        return False
    drop_pct = (r.price_90d_ago - r.price_usd) / r.price_90d_ago * 100
    return drop_pct > config.PRICE_CRASH_DROP_PCT


def rollup_to_brands(asins: list[AsinRecord]) -> list[BrandRecord]:
    """Group qualifying ASINs by brand; apply brand-level rules."""
    groups: dict[str, list[AsinRecord]] = defaultdict(list)
    for a in asins:
        groups[a.brand].append(a)

    brands = []
    for brand_name, items in groups.items():
        avg_price = sum(i.price_usd for i in items) / len(items)
        avg_sellers = sum(i.seller_count for i in items) / len(items)
        avg_amazon_pct = sum(i.amazon_present_pct for i in items) / len(items)
        total_units = sum(i.units_per_month for i in items)

        # Revenue estimate: avg price × total units
        est_revenue = avg_price * total_units

        if not (config.MIN_BRAND_REVENUE <= est_revenue <= config.MAX_BRAND_REVENUE):
            log.debug("Drop brand %s: revenue=%.0f", brand_name, est_revenue)
            continue

        categories = list({i.category for i in items if i.category})

        brand = BrandRecord(
            name=brand_name,
            parent=brand_name,       # populated later if parent lookup added
            domain="",               # populated by contact finder
            est_monthly_revenue=est_revenue,
            avg_sellers=avg_sellers,
            amazon_present_pct=avg_amazon_pct,
            qualifying_asins=len(items),
            units_per_month=total_units,
            score=0.0,
            categories=categories,
        )
        brands.append(brand)

    log.info("Brand rollup: %d brands qualify", len(brands))
    return brands


def score_and_rank(brands: list[BrandRecord]) -> list[BrandRecord]:
    """
    Score descending by:
      amazon_absent (weight 4) + fewest_sellers (3) + revenue_health (2) + price_stability (1)
    """
    if not brands:
        return brands

    max_sellers = max(b.avg_sellers for b in brands) or 1
    max_revenue = max(b.est_monthly_revenue for b in brands) or 1

    for b in brands:
        amazon_absent = (100 - b.amazon_present_pct) / 100 * 4
        few_sellers = (1 - b.avg_sellers / max_sellers) * 3
        rev_health = (b.est_monthly_revenue / max_revenue) * 2
        b.score = round(amazon_absent + few_sellers + rev_health, 3)

    brands.sort(key=lambda b: b.score, reverse=True)
    return brands
