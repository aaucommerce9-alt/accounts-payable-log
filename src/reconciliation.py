"""
Reconciliation: compare tool-computed net total vs Amazon's actual payout.

For each settlement group we know the actual deposited amount (from the
FinancialEventGroup's ConvertedTotal). After summing our captured rows for
that group, we compare to the cent.
"""

import logging

logger = logging.getLogger(__name__)


def reconcile_group(
    group: dict,
    rows: list[dict],
    tolerance_usd: float = 0.01,
) -> dict:
    """
    group  — one item from listFinancialEventGroups (raw SP-API payload)
    rows   — all transaction rows we captured for this settlement group
    Returns a result dict with 'status', 'delta', and any gap details.
    """
    group_id    = group.get("FinancialEventGroupId", "")
    fund_info   = group.get("ConvertedTotal", {})
    actual_payout = float(fund_info.get("CurrencyAmount", 0) or 0)

    computed_net = round(sum(r.get("net_proceeds", 0) for r in rows), 2)
    delta        = round(computed_net - actual_payout, 2)
    abs_delta    = abs(delta)

    if abs_delta <= tolerance_usd:
        status = "VERIFIED"
        logger.info(
            "Settlement %s VERIFIED. Computed=%.2f  Amazon=%.2f  Delta=%.4f",
            group_id, computed_net, actual_payout, delta
        )
    else:
        status = "DISCREPANCY"
        logger.warning(
            "Settlement %s DISCREPANCY! Computed=%.2f  Amazon=%.2f  Delta=%.2f",
            group_id, computed_net, actual_payout, delta
        )
        _diagnose_gap(rows, delta)

    return {
        "group_id":       group_id,
        "status":         status,
        "computed_net":   computed_net,
        "actual_payout":  actual_payout,
        "delta":          delta,
    }


def _diagnose_gap(rows: list[dict], delta: float):
    """Log a breakdown of what's in the captured rows to help pinpoint the gap."""
    from collections import defaultdict
    by_type: dict[str, float] = defaultdict(float)
    for r in rows:
        by_type[r.get("type", "unknown")] += r.get("net_proceeds", 0)

    logger.warning("  Gap of %.2f — breakdown of captured rows by type:", delta)
    for txn_type, total in sorted(by_type.items()):
        logger.warning("    %-20s  %.2f", txn_type, total)
    logger.warning("  Check the sync log for any UNKNOWN event types that were skipped.")


def reconcile_all(groups: list[dict], rows_by_group: dict[str, list[dict]],
                  tolerance_usd: float = 0.01) -> list[dict]:
    results = []
    for group in groups:
        gid  = group.get("FinancialEventGroupId", "")
        rows = rows_by_group.get(gid, [])
        results.append(reconcile_group(group, rows, tolerance_usd))
    return results


def print_reconciliation_report(results: list[dict]):
    print("\n" + "=" * 60)
    print("  RECONCILIATION REPORT")
    print("=" * 60)
    any_fail = False
    for r in results:
        mark = "✓" if r["status"] == "VERIFIED" else "✗"
        print(f"  [{mark}] Settlement {r['group_id']}")
        print(f"       Computed : ${r['computed_net']:>12.2f}")
        print(f"       Amazon   : ${r['actual_payout']:>12.2f}")
        print(f"       Delta    : ${r['delta']:>12.2f}  [{r['status']}]")
        print()
        if r["status"] != "VERIFIED":
            any_fail = True
    if any_fail:
        print("  *** ACTION REQUIRED: One or more settlements do not reconcile. ***")
        print("  *** Review the sync log for flagged unknown transaction types. ***")
    else:
        print("  All settlements verified.")
    print("=" * 60 + "\n")
