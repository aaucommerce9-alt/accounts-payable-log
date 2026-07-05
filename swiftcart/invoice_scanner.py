"""Invoice → Amazon profitability scan.

Flow: parse invoice → look up ASINs by UPC (Keepa) → run FBA/FBM profit
calc → verdict per SKU, sorted best-profit first.
"""
import logging

from .invoice_parser import parse_invoice
from .keepa_client import fetch_asin_details_by_upc
from .models import SkuEvaluation
from .profit_calculator import evaluate_sku

log = logging.getLogger(__name__)


def scan_invoice(path: str, channel: str = "FBA") -> list[SkuEvaluation]:
    line_items = parse_invoice(path)
    if not line_items:
        log.warning("No line items parsed from %s", path)
        return []

    upcs = [item.upc for item in line_items]
    asin_by_upc = fetch_asin_details_by_upc(upcs)

    results = []
    unmatched = 0
    for item in line_items:
        rec = asin_by_upc.get(item.upc)
        if not rec:
            unmatched += 1
            continue
        results.append(evaluate_sku(item, rec, channel))

    results.sort(key=lambda r: r.profit_per_unit, reverse=True)
    log.info(
        "Scanned %d line items → %d matched to Amazon, %d unmatched",
        len(line_items), len(results), unmatched,
    )
    return results
