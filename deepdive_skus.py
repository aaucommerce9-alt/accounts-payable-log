"""Deep-dive Keepa lookup for a shortlist of ASINs.

Pulls offers + price/rank history (not used in the bulk invoice scan, to
keep token cost down there) for a small set of promising near-miss SKUs,
so you can see real seller count / competition and Amazon's own
monthly-sold estimate before deciding whether they're worth buying.

Queries Keepa directly rather than going through fetch_asin_details(),
which requires a non-empty `brand` field (needed for the brand-outreach
pipeline it was built for) and silently drops anything without one —
private-label items like these HDS SKUs often have no brand in Keepa.
"""
import argparse
import csv

from swiftcart import config
import keepa

AMAZON_SELLER_ID = "ATVPDKIKX0DER"


def parse_product(p):
    asin = p.get("asin", "")
    stats = p.get("stats") or {}
    current = stats.get("current") or []
    price_cents = current[1] if len(current) > 1 else None
    price_usd = (price_cents / 100.0) if (price_cents and price_cents > 0) else 0.0

    bsr = current[3] if len(current) > 3 else None
    bsr = int(bsr) if bsr and bsr > 0 else 0

    monthly_sold = p.get("monthlySold") or 0

    offers = p.get("offers") or []
    seller_count = len([o for o in offers if o.get("isFBA") or o.get("isMerchant")])

    buybox_seller = stats.get("buyBoxSellerId") or p.get("buyBoxSellerId")
    amazon_is_buybox = buybox_seller == AMAZON_SELLER_ID

    category = (p.get("categoryTree") or [{}])[-1].get("name", "")

    # amazon present %: fraction of csv[0] (Amazon price history) with a real price
    try:
        csv_data = p.get("csv") or []
        amazon_hist = csv_data[0] if csv_data else []
        prices = amazon_hist[1::2] if amazon_hist else []
        amazon_pct = round(100 * sum(1 for v in prices if v and v > 0) / len(prices), 1) if prices else 0.0
    except Exception:
        amazon_pct = 0.0

    return {
        "asin": asin, "price_usd": price_usd, "bsr": bsr,
        "monthly_sold": int(monthly_sold), "seller_count": seller_count,
        "amazon_is_buybox": amazon_is_buybox, "amazon_pct": amazon_pct,
        "category": category, "title": (p.get("title") or "").strip(),
    }


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
    api = keepa.Keepa(config.KEEPA_API_KEY)
    products = api.query(asins, stats=90, offers=20, history=True, wait=True)
    print(f"Got {len(products)} products back from Keepa")

    with open(args.csv_out, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow([
            "ASIN", "UPC", "Description", "Cost", "Sell Price",
            "Seller Count", "Amazon Present %", "Amazon Is Buybox",
            "Monthly Sold (Keepa)", "BSR", "Category", "Title",
        ])
        for p in products:
            rec = parse_product(p)
            orig = cost_by_asin.get(rec["asin"], {})
            w.writerow([
                rec["asin"],
                orig.get("UPC", ""),
                orig.get("Description", ""),
                orig.get("Cost", ""),
                rec["price_usd"],
                rec["seller_count"],
                rec["amazon_pct"],
                rec["amazon_is_buybox"],
                rec["monthly_sold"],
                rec["bsr"],
                rec["category"],
                rec["title"],
            ])

    print("Wrote", args.csv_out)


if __name__ == "__main__":
    main()
