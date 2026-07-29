"""
check_asins.py — Quick competition check on any ASINs.

Usage:
    python check_asins.py B008TMGI1Q B0BX78K4RV B07TS4HW4Y

Reads KEEPA_API_KEY from .env file automatically.
"""
import sys
import os
from dotenv import load_dotenv
import keepa

load_dotenv()

asins = sys.argv[1:]
if not asins:
    print("Usage: python check_asins.py ASIN1 ASIN2 ASIN3 ...")
    sys.exit(1)

key = os.getenv("KEEPA_API_KEY", "")
if not key:
    print("ERROR: KEEPA_API_KEY not found in .env file")
    sys.exit(1)

print(f"Looking up {len(asins)} ASINs...")
api = keepa.Keepa(key)
products = api.query(asins, stats=90, history=True, domain="US")

print()
for p in products:
    cur = (p.get("stats") or {}).get("current") or []
    avg30 = (p.get("stats") or {}).get("avg30") or []

    def c(arr, i):
        try:
            v = arr[i]
            return f"${v/100:.2f}" if v and v > 0 else None
        except:
            return None

    def n(arr, i):
        try:
            v = arr[i]
            return int(v) if v and v > 0 else 0
        except:
            return 0

    csv = p.get("csv") or []
    amazon_hist = csv[0] if csv else []
    amazon_prices = amazon_hist[1::2] if amazon_hist else []
    if any(v and v > 0 for v in amazon_prices):
        amazon = "YES (was/is on listing) ⚠️"
    else:
        amazon = "NO — never on listing ✓"

    price = c(cur, 1) or c(avg30, 1) or "N/A"
    sellers = n(cur, 11) or n(avg30, 11)
    rank = n(cur, 3)
    monthly = p.get("monthlySold") or 0

    print("=" * 60)
    print(f"ASIN:     {p.get('asin')}")
    print(f"Brand:    {p.get('brand', '?')}")
    print(f"Title:    {(p.get('title') or '')[:55]}")
    print(f"Price:    {price}")
    print(f"Sellers:  {sellers}")
    print(f"Amazon:   {amazon}")
    print(f"Rank:     {rank:,}" if rank else "Rank:     N/A")
    print(f"Monthly:  ~{monthly} units")
    print()
