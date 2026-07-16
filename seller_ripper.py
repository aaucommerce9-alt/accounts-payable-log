"""
seller_ripper.py — Find wholesale-approved brands by cross-referencing seller storefronts.

Logic: if multiple known wholesalers carry the same brand, that brand likely
approves wholesale accounts. Output is brands.csv sorted by how many of your
sellers carry it.

Usage:
    KEEPA_KEY=your_key python seller_ripper.py

How to find seller IDs:
    Go to any Amazon listing → click the seller name → look at the URL:
    https://www.amazon.com/sp?seller=A1EXAMPLE123
    The value after "seller=" is the seller ID (starts with A, ~14 chars).
    Add known wholesalers/distributors you already buy from.
"""
import csv
import logging
import os
import sqlite3
import time
from collections import defaultdict
from datetime import datetime, timedelta

import keepa

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

# ── Edit this list with your known wholesaler/distributor seller IDs ──────────
SELLER_IDS = [
    # "A1EXAMPLE123456",   # Wholesaler A
    # "B2EXAMPLE789012",   # Wholesaler B
    # Add more here
]

# ── Config ────────────────────────────────────────────────────────────────────
CACHE_DB = "seller_ripper_cache.db"
CACHE_TTL_DAYS = 7
ASIN_BATCH_SIZE = 100
MIN_SELLERS_OVERLAP = 2   # only show brands carried by this many sellers

# Filters — a product "passes" if ALL three are true:
MIN_PRICE_USD = 15.00
MIN_OFFER_COUNT = 3
MAX_OFFER_COUNT = 10

# Keepa API indices (verified from keepa.csv_indices):
#   csv[0]  = AMAZON price history  (cents; -1 = absent)
#   csv[1]  = NEW price history     (cents; -1 = absent)
#   csv[11] = COUNT_NEW (3P seller count, raw integer, not price)
# stats.current[] mirrors the same indices.
IDX_AMAZON = 0
IDX_NEW_PRICE = 1
IDX_COUNT_NEW = 11


# ── Cache ─────────────────────────────────────────────────────────────────────

def _db() -> sqlite3.Connection:
    con = sqlite3.connect(CACHE_DB)
    con.execute("""
        CREATE TABLE IF NOT EXISTS cache (
            key TEXT PRIMARY KEY,
            value TEXT,
            cached_at TEXT
        )
    """)
    con.commit()
    return con


def _cache_get(con: sqlite3.Connection, key: str):
    row = con.execute(
        "SELECT value, cached_at FROM cache WHERE key = ?", (key,)
    ).fetchone()
    if not row:
        return None
    cached_at = datetime.fromisoformat(row[1])
    if datetime.utcnow() - cached_at > timedelta(days=CACHE_TTL_DAYS):
        return None
    import json
    return json.loads(row[0])


def _cache_set(con: sqlite3.Connection, key: str, value) -> None:
    import json
    con.execute(
        "INSERT OR REPLACE INTO cache (key, value, cached_at) VALUES (?, ?, ?)",
        (key, json.dumps(value), datetime.utcnow().isoformat()),
    )
    con.commit()


# ── Token guard ───────────────────────────────────────────────────────────────

def _wait_tokens(api: keepa.Keepa, needed: int = 10) -> None:
    """Block until the API has at least `needed` tokens."""
    api.update_status()
    while api.tokens_left < needed:
        wait = max(api.time_to_refill, 5)
        log.warning("Only %d tokens left, need %d — waiting %.0fs", api.tokens_left, needed, wait)
        time.sleep(wait)
        api.update_status()


# ── Keepa calls ───────────────────────────────────────────────────────────────

def get_seller_asins(api: keepa.Keepa, con: sqlite3.Connection, seller_id: str) -> list[str]:
    cache_key = f"seller:{seller_id}"
    cached = _cache_get(con, cache_key)
    if cached is not None:
        log.info("Seller %s: %d ASINs (cached)", seller_id, len(cached))
        return cached

    _wait_tokens(api, needed=20)
    log.info("Fetching storefront for seller %s ...", seller_id)
    for attempt in range(3):
        try:
            result = api.seller_query(seller_id, domain="US", storefront=True)
            seller_data = result.get(seller_id, {})
            asins = list(seller_data.get("asinList") or [])
            log.info("Seller %s: %d ASINs fetched", seller_id, len(asins))
            _cache_set(con, cache_key, asins)
            return asins
        except Exception as exc:
            log.warning("Seller %s attempt %d failed: %s", seller_id, attempt + 1, exc)
            time.sleep(2 ** attempt * 3)
    log.error("Seller %s: all attempts failed, skipping", seller_id)
    return []


def get_product_details(api: keepa.Keepa, con: sqlite3.Connection, asins: list[str]) -> list[dict]:
    results = []
    to_fetch = []

    for asin in asins:
        cached = _cache_get(con, f"asin:{asin}")
        if cached is not None:
            results.append(cached)
        else:
            to_fetch.append(asin)

    log.info("%d ASINs from cache, %d to fetch", len(results), len(to_fetch))

    for i in range(0, len(to_fetch), ASIN_BATCH_SIZE):
        chunk = to_fetch[i: i + ASIN_BATCH_SIZE]
        _wait_tokens(api, needed=len(chunk) * 2)
        log.info("Fetching products %d–%d of %d ...", i + 1, i + len(chunk), len(to_fetch))
        for attempt in range(3):
            try:
                products = api.query(chunk, stats=365, history=True, domain="US")
                for p in (products or []):
                    rec = _extract(p)
                    if rec:
                        _cache_set(con, f"asin:{rec['asin']}", rec)
                        results.append(rec)
                break
            except Exception as exc:
                log.warning("Product batch attempt %d failed: %s", attempt + 1, exc)
                time.sleep(2 ** attempt * 5)

    return results


def _extract(p: dict) -> dict | None:
    """Pull the fields we need from a Keepa product object."""
    try:
        asin = p.get("asin") or ""
        brand = (p.get("brand") or "").strip()
        if not asin or not brand:
            return None

        stats = p.get("stats") or {}
        current = stats.get("current") or []

        # Current new price (cents → USD); -1 = not available
        def _cents(arr, idx):
            try:
                v = arr[idx]
                return v / 100.0 if v and v > 0 else 0.0
            except (IndexError, TypeError):
                return 0.0

        def _int_stat(arr, idx):
            try:
                v = arr[idx]
                return int(v) if v and v > 0 else 0
            except (IndexError, TypeError):
                return 0

        price_usd = _cents(current, IDX_NEW_PRICE)
        offer_count = _int_stat(current, IDX_COUNT_NEW)

        # Amazon-never-present check: scan the full AMAZON price history (csv[0]).
        # csv arrays are stored as interleaved [time, value, time, value, ...].
        # Values at odd positions are prices in cents; -1 means Amazon was absent
        # at that timestamp. If every recorded value is -1, Amazon was never present.
        csv = p.get("csv") or []
        amazon_history = csv[IDX_AMAZON] if len(csv) > IDX_AMAZON else None
        if amazon_history:
            # Odd-indexed elements (1, 3, 5, ...) are the price values
            amazon_prices = amazon_history[1::2]
            amazon_ever_present = any(v != -1 for v in amazon_prices)
        else:
            # No history at all → treat as never present
            amazon_ever_present = False

        return {
            "asin": asin,
            "brand": brand,
            "price_usd": price_usd,
            "offer_count": offer_count,
            "amazon_ever_present": amazon_ever_present,
        }
    except Exception as exc:
        log.debug("Failed to extract %s: %s", p.get("asin"), exc)
        return None


# ── Filters ───────────────────────────────────────────────────────────────────

def passes_filters(rec: dict) -> bool:
    if rec["amazon_ever_present"]:
        return False                            # Amazon was on this at some point
    if rec["price_usd"] < MIN_PRICE_USD:
        return False
    if not (MIN_OFFER_COUNT <= rec["offer_count"] <= MAX_OFFER_COUNT):
        return False
    return True


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    if not SELLER_IDS:
        print("ERROR: Add seller IDs to the SELLER_IDS list at the top of this file.")
        return

    key = os.environ.get("KEEPA_KEY", "")
    if not key:
        raise EnvironmentError("Set KEEPA_KEY environment variable before running.")

    api = keepa.Keepa(key)
    con = _db()

    # seller_id → set of ASINs
    seller_asins: dict[str, set[str]] = {}
    for seller_id in SELLER_IDS:
        asins = get_seller_asins(api, con, seller_id)
        seller_asins[seller_id] = set(asins)

    all_asins = set().union(*seller_asins.values())
    log.info("Total unique ASINs across all sellers: %d", len(all_asins))

    products = get_product_details(api, con, list(all_asins))
    log.info("Products fetched/cached: %d", len(products))

    # asin → product record (for quick lookup)
    by_asin: dict[str, dict] = {p["asin"]: p for p in products}

    # brand → set of seller IDs that carry it
    brand_sellers: dict[str, set[str]] = defaultdict(set)
    brand_asins_total: dict[str, int] = defaultdict(int)
    brand_asins_passing: dict[str, int] = defaultdict(int)

    for seller_id, asins in seller_asins.items():
        for asin in asins:
            rec = by_asin.get(asin)
            if not rec:
                continue
            brand = rec["brand"]
            brand_sellers[brand].add(seller_id)
            brand_asins_total[brand] += 1
            if passes_filters(rec):
                brand_asins_passing[brand] += 1

    # Build output rows
    rows = []
    for brand, sellers in brand_sellers.items():
        passing = brand_asins_passing[brand]
        if passing == 0:
            continue
        rows.append({
            "brand": brand,
            "sellers_carrying": len(sellers),
            "asins_passing": passing,
            "asins_total": brand_asins_total[brand],
        })

    rows.sort(key=lambda r: (-r["sellers_carrying"], -r["asins_passing"]))

    # Write CSV
    out_file = "brands.csv"
    with open(out_file, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["brand", "sellers_carrying", "asins_passing", "asins_total"])
        writer.writeheader()
        writer.writerows(rows)

    print(f"\nWrote {len(rows)} brands to {out_file}\n")
    print(f"{'Brand':<40} {'Sellers':>7} {'Passing':>8} {'Total':>6}")
    print("-" * 65)
    for row in rows[:20]:
        print(f"{row['brand']:<40} {row['sellers_carrying']:>7} {row['asins_passing']:>8} {row['asins_total']:>6}")


if __name__ == "__main__":
    main()
