#!/usr/bin/env python3
"""
CLI entry point for the invoice → Amazon profitability scanner.

Usage:
    python scan_invoice.py path/to/invoice.csv --channel FBA
    python scan_invoice.py path/to/invoice.xlsx --channel FBM --sheet
"""
import argparse
import logging
import sys

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s — %(message)s",
)

from swiftcart import sheets_client
from swiftcart.invoice_scanner import scan_invoice


def main() -> None:
    parser = argparse.ArgumentParser(description="Scan an invoice for Amazon-resale profitability")
    parser.add_argument("invoice", help="Path to invoice PDF/Excel/CSV")
    parser.add_argument("--channel", choices=["FBA", "FBM"], default="FBA", help="Fulfillment channel")
    parser.add_argument("--sheet", action="store_true", help="Also write results to the Google Sheet")
    args = parser.parse_args()

    results = scan_invoice(args.invoice, channel=args.channel)

    if not results:
        print("No SKUs matched to Amazon listings.")
        sys.exit(0)

    print(f"\n{'UPC':<14}{'ASIN':<12}{'Sell':>8}{'Cost':>8}{'Fees':>8}{'Profit':>8}{'Margin%':>9}{'ROI%':>8}  Verdict")
    print("-" * 100)
    for r in results:
        fees = r.referral_fee + r.fulfillment_fee
        print(
            f"{r.upc:<14}{r.asin:<12}{r.sell_price:>8.2f}{r.cost_per_unit:>8.2f}"
            f"{fees:>8.2f}{r.profit_per_unit:>8.2f}{r.margin_pct:>9.1f}{r.roi_pct:>8.1f}  {r.verdict}"
        )

    buys = sum(1 for r in results if r.verdict == "buy")
    print(f"\n{buys}/{len(results)} SKUs are BUY at current thresholds.")

    if args.sheet:
        try:
            sheets_client.write_invoice_results(results)
            print("Results written to Google Sheet.")
        except Exception as exc:
            print(f"Sheet write failed: {exc}")


if __name__ == "__main__":
    main()
