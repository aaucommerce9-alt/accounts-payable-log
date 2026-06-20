#!/usr/bin/env python3
"""
Amazon Bookkeeping Auto-Sync Tool — v1
Entry point: run on-demand or via cron/Task Scheduler.

Usage:
    python main.py                    # one-shot sync
    python main.py --schedule         # run once now, then daily at midnight
    python main.py --reset-sync       # forget last-synced marker and re-pull everything
    python main.py --reconcile-only   # skip new data pull; just re-run reconciliation
    python main.py --config path/to/config.yaml
"""

import argparse
import logging
import sys
import time
from datetime import datetime, timezone

import schedule

from src import config_loader, sync_state, logger_setup
from src.sp_api_client import SPAPIClient
from src.transactions import from_financial_events, dedup
from src.bookkeeping import load_cost_master, apply_calculations
from src.excel_writer import append_transactions, refresh_monthly_summary
from src.reconciliation import reconcile_all, print_reconciliation_report


def run_sync(cfg: dict):
    logger = logging.getLogger(__name__)
    logger.info("=" * 55)
    logger.info("  Amazon Bookkeeping Sync — %s",
                datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"))
    logger.info("=" * 55)

    # ------------------------------------------------------------------ #
    # 1. Load state + credentials
    # ------------------------------------------------------------------ #
    state_path = cfg["paths"]["sync_state"]
    state      = sync_state.load(state_path, cfg["sync"]["initial_lookback_days"])
    last_sync  = state["last_synced"]

    seen_ids: set[str] = set(state.get("synced_transaction_ids", []))
    reconciled_groups:  set[str] = set(state.get("reconciled_group_ids", []))

    client = SPAPIClient(cfg)

    # ------------------------------------------------------------------ #
    # 2. Fetch financial event groups (settlement cycles)
    # ------------------------------------------------------------------ #
    logger.info("Fetching financial event groups since %s …", last_sync)
    groups = client.list_financial_event_groups(posted_after=last_sync)

    all_new_rows:   list[dict]         = []
    rows_by_group:  dict[str, list]    = {}

    for group in groups:
        gid = group.get("FinancialEventGroupId", "")
        logger.info("Processing group %s …", gid)

        events = client.list_financial_events_by_group(gid)
        raw_rows = from_financial_events(events, settlement_id=gid)

        new_rows = dedup(raw_rows, seen_ids)
        rows_by_group[gid] = new_rows
        all_new_rows.extend(new_rows)

    # ------------------------------------------------------------------ #
    # 3. Also pull any un-grouped financial events (recent orders)
    # ------------------------------------------------------------------ #
    logger.info("Fetching un-grouped financial events since %s …", last_sync)
    ungrouped_events = client.list_financial_events(posted_after=last_sync)
    ungrouped_rows   = from_financial_events(ungrouped_events, settlement_id="")
    new_ungrouped    = dedup(ungrouped_rows, seen_ids)
    all_new_rows.extend(new_ungrouped)
    rows_by_group.setdefault("(ungrouped)", []).extend(new_ungrouped)

    logger.info("Total new transactions captured: %d", len(all_new_rows))

    # ------------------------------------------------------------------ #
    # 4. Apply COGS + profit-share calculations
    # ------------------------------------------------------------------ #
    wb_path  = cfg["paths"]["workbook"]
    cost_map = load_cost_master(wb_path, cfg)
    all_new_rows = apply_calculations(all_new_rows, cost_map, cfg)

    # ------------------------------------------------------------------ #
    # 5. Write to Excel
    # ------------------------------------------------------------------ #
    written = append_transactions(all_new_rows, wb_path, cfg)
    if written > 0:
        refresh_monthly_summary(wb_path, cfg)

    # ------------------------------------------------------------------ #
    # 6. Reconciliation
    # ------------------------------------------------------------------ #
    tolerance = cfg["reconciliation"]["tolerance_usd"]
    unreconciled_groups = [g for g in groups
                           if g.get("FinancialEventGroupId") not in reconciled_groups
                           and g.get("FundTransferStatus") == "CLOSED"]

    if unreconciled_groups:
        results = reconcile_all(unreconciled_groups, rows_by_group, tolerance)
        print_reconciliation_report(results)
        for r in results:
            if r["status"] == "VERIFIED":
                reconciled_groups.add(r["group_id"])
    else:
        logger.info("No newly closed settlement groups to reconcile.")

    # ------------------------------------------------------------------ #
    # 7. Persist state
    # ------------------------------------------------------------------ #
    sync_state.mark_now(state)
    state["synced_transaction_ids"] = list(seen_ids)
    state["reconciled_group_ids"]   = list(reconciled_groups)
    sync_state.save(state_path, state)

    logger.info("Sync complete. %d rows written, %d groups reconciled.",
                written, len(unreconciled_groups))


def main():
    parser = argparse.ArgumentParser(description="Amazon Bookkeeping Sync Tool")
    parser.add_argument("--config",         default="config.yaml",
                        help="Path to config.yaml (default: ./config.yaml)")
    parser.add_argument("--schedule",       action="store_true",
                        help="Run continuously on a daily schedule")
    parser.add_argument("--reset-sync",     action="store_true",
                        help="Delete last-sync marker and pull from initial lookback window")
    parser.add_argument("--reconcile-only", action="store_true",
                        help="Re-run reconciliation against existing Excel data only")
    args = parser.parse_args()

    cfg = config_loader.load(args.config)
    logger_setup.setup(cfg["paths"]["sync_log"])
    logger = logging.getLogger(__name__)

    if args.reset_sync:
        import os
        try:
            os.remove(cfg["paths"]["sync_state"])
            logger.info("Sync state reset.")
        except FileNotFoundError:
            pass

    if args.reconcile_only:
        logger.info("Reconcile-only mode — reading existing workbook …")
        # Load all rows from Excel and re-run reconciliation
        # (useful after manual corrections)
        import openpyxl
        from src.excel_writer import _col_map
        wb  = openpyxl.load_workbook(cfg["paths"]["workbook"], read_only=True, data_only=True)
        ws  = wb[cfg["excel"]["transactions_tab"]]
        cols = _col_map(cfg)
        rows = []
        for row in ws.iter_rows(min_row=2, values_only=True):
            rows.append({
                "net_proceeds":  float(row[cols["net_proceeds"] - 1] or 0),
                "settlement_id": row[cols["settlement_id"] - 1] or "",
            })
        wb.close()
        by_group: dict[str, list] = {}
        for r in rows:
            by_group.setdefault(r["settlement_id"], []).append(r)
        client = SPAPIClient(cfg)
        state  = sync_state.load(cfg["paths"]["sync_state"])
        groups = client.list_financial_event_groups(state["last_synced"])
        results = reconcile_all(groups, by_group, cfg["reconciliation"]["tolerance_usd"])
        print_reconciliation_report(results)
        return

    if args.schedule:
        logger.info("Scheduled mode: running now, then daily at 00:00 UTC.")
        run_sync(cfg)
        schedule.every().day.at("00:00").do(run_sync, cfg=cfg)
        while True:
            schedule.run_pending()
            time.sleep(60)
    else:
        run_sync(cfg)


if __name__ == "__main__":
    main()
