"""Deep-dive Keepa lookup for a shortlist of ASINs.

Pulls offers + price/rank history (not used in the bulk invoice scan, to
keep token cost down there) for a small set of promising near-miss SKUs,
so you can see real seller count / competition and Amazon's own
monthly-sold estimate before deciding whether they're worth buying.
"""
import argparse
import csv

from swiftcart.keepa_client import fetch_asin_details


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("input_csv", help="CSV with at least an ASIN column")
    parser.add_argument("--csv-out", required=True)
    args = parser.parse_args()

    with open(args.input_csv, newline="") as f:
        rows = list(csv.DictReader(f))

    asins = [r["ASIN"] for r in rows if r.get("ASIN")]
    cost_by_asin = {r["ASIN"]: r for r in rows}

    print(f"Deep-diving {len(asins)} ASINs...")
    records = fetch_asin_details(asins)
    print(f"Got data back for {len(records)}/{len(asins)}")

    with open(args.csv_out, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow([
            "ASIN", "UPC", "Description", "Cost", "Sell Price",
            "Seller Count", "Amazon Present %", "Amazon Is Buybox",
            "Monthly Sold (Keepa)", "BSR", "Category",
        ])
        for rec in records:
            orig = cost_by_asin.get(rec.asin, {})
            w.writerow([
                rec.asin,
                orig.get("UPC", ""),
                orig.get("Description", ""),
                orig.get("Cost", ""),
                rec.price_usd,
                rec.seller_count,
                rec.amazon_present_pct,
                rec.amazon_is_buybox,
                rec.units_per_month,
                rec.bsr,
                rec.category,
            ])

    print("Wrote", args.csv_out)


if __name__ == "__main__":
    main()
