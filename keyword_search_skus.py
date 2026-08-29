"""Keyword-based Amazon matching for catalogs with no UPC and no price.

Some supplier catalogs (e.g. AB_Catalog / ACM_Catalog) list only an item
code, a free-text description, and a case pack — no barcode, no cost.
Without a UPC, exact Keepa lookup isn't possible, and without a cost,
profit/margin/ROI can't be computed at all. So instead of a buy/no-buy
verdict, this ranks items by Amazon sales velocity (BSR / monthly units
sold) and how little Amazon itself competes on the listing, using
Keepa's Product Finder keyword search against the free-text description.

Two-phase design to keep cost predictable:
  1. One product_finder() search per catalog item (cheap, ASIN-list only)
     to find the best-matching Amazon listing for that description.
  2. One batched query() (100 ASINs/request, same as the UPC pipeline)
     for the small deduped set of matched ASINs, to pull real stats.
"""
import argparse
import csv
import json
import re
import time

import requests

from swiftcart import config
import keepa

AMAZON_SELLER_ID = "ATVPDKIKX0DER"

STOPWORDS = {
    "the", "and", "for", "with", "in", "of", "a", "an", "to", "on", "by",
    "or", "new", "asst", "assorted", "each", "per", "case", "pack",
}

# Vertical sidebar category labels from the AB/ACM catalog layout sometimes
# bleed into the item's text block mirror-reversed (e.g. "LAUNDRY" ->
# "YRDNUAL", see ab_acm_clean.csv cleanup) — only strip the reversed form,
# since the forward word (e.g. "Liquid", "Laundry") is often a real,
# useful part of the product description.
_CATEGORY_NOISE = {
    "laundry", "liquid", "household", "health", "hand", "beauty",
    "personal", "care", "home", "kitchen", "cleaning", "cleaners",
}
NOISE_WORDS = {w[::-1] for w in _CATEGORY_NOISE}

# size/measurement tokens that mean nothing to an Amazon title search
UNIT_RE = re.compile(
    r"^\d+(\.\d+)?\s*(oz|ml|l|lb|lbs|g|kg|ct|pk|pc|pcs|fl|floz|gal|qt|pt|x|w|"
    r"in|inch|inches|cm|mm)?\.?,?$",
    re.IGNORECASE,
)
BRACKET_RE = re.compile(r"[\{\[(].*?[\}\])]")


def build_search_title(description: str, max_words: int = 6) -> str:
    text = BRACKET_RE.sub(" ", description)
    text = re.sub(r"[^A-Za-z0-9\s]", " ", text)
    words = []
    for tok in text.split():
        if UNIT_RE.match(tok):
            continue
        if tok.lower() in STOPWORDS or tok.lower() in NOISE_WORDS:
            continue
        if len(tok) < 2:
            continue
        words.append(tok)
        if len(words) >= max_words:
            break
    return " ".join(words)


def _raw_product_finder(api: keepa.Keepa, selection: dict) -> tuple[list[str], str | None]:
    """Bypass the keepa library's product_finder() to get the actual error
    body on a non-200 response — the library only surfaces a generic
    status-code name (e.g. 'REQUEST_REJECTED'), not why."""
    payload = {
        "key": api.accesskey,
        "domain": 1,  # US
        "selection": json.dumps(selection),
    }
    try:
        r = requests.get("https://api.keepa.com/query", params=payload, timeout=30)
    except Exception as exc:
        return [], f"network error: {exc}"
    try:
        data = r.json()
    except Exception:
        return [], f"non-JSON response (status {r.status_code}): {r.text[:300]}"
    if "tokensLeft" in data:
        api.tokens_left = data["tokensLeft"]
    if r.status_code != 200:
        return [], f"status {r.status_code}: {data.get('error') or data}"
    return data.get("asinList") or [], None


# Keepa rejects a product_finder request outright ("combination of perPage
# and page exceeds limit or is too small") if perPage is set too low —
# 50 is the library's own default and the practical floor. Ask for that
# many and just slice locally to the few we actually want.
FINDER_PER_PAGE = 50


def find_candidates(api: keepa.Keepa, title_query: str, n: int = 3) -> list[str]:
    if not title_query:
        return []
    n_terms = len(title_query.split())
    min_match = max(1, min(3, n_terms - 1)) if n_terms > 1 else 1

    # Try progressively simpler selections — some field combos Keepa's
    # Product Finder rejects outright (400) without a helpful message
    # through the library, so fall back rather than losing the item.
    attempts = [
        {"title": title_query, "minMatch": {"title": min_match},
         "sort": [["current_SALES", "asc"]], "perPage": FINDER_PER_PAGE, "page": 0},
        {"title": title_query, "sort": [["current_SALES", "asc"]], "perPage": FINDER_PER_PAGE, "page": 0},
        {"title": title_query, "perPage": FINDER_PER_PAGE, "page": 0},
    ]
    last_err = None
    for attempt in attempts:
        asins, err = _raw_product_finder(api, attempt)
        if err is None:
            return asins[:n]
        last_err = err
    print(f"  product_finder failed for {title_query!r}: {last_err}")
    return []


def parse_product(p: dict) -> dict:
    asin = p.get("asin", "")
    stats = p.get("stats") or {}
    current = stats.get("current") or []
    price_cents = current[1] if len(current) > 1 else None
    price_usd = (price_cents / 100.0) if (price_cents and price_cents > 0) else 0.0

    bsr = current[3] if len(current) > 3 else None
    bsr = int(bsr) if bsr and bsr > 0 else 0

    monthly_sold = int(p.get("monthlySold") or 0)

    offers = p.get("offers") or []
    seller_count = len([o for o in offers if o.get("isFBA") or o.get("isMerchant")])

    buybox_seller = stats.get("buyBoxSellerId") or p.get("buyBoxSellerId")
    amazon_is_buybox = buybox_seller == AMAZON_SELLER_ID

    category = (p.get("categoryTree") or [{}])[-1].get("name", "")

    try:
        csv_data = p.get("csv") or []
        amazon_hist = csv_data[0] if csv_data else []
        prices = amazon_hist[1::2] if amazon_hist else []
        amazon_pct = round(100 * sum(1 for v in prices if v and v > 0) / len(prices), 1) if prices else 0.0
    except Exception:
        amazon_pct = 0.0

    return {
        "asin": asin, "price_usd": price_usd, "bsr": bsr,
        "monthly_sold": monthly_sold, "seller_count": seller_count,
        "amazon_is_buybox": amazon_is_buybox, "amazon_pct": amazon_pct,
        "category": category, "title": (p.get("title") or "").strip(),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("input_csv", help="CSV with ItemCode,Description,CasePack,Source columns")
    parser.add_argument("--csv-out", required=True)
    parser.add_argument("--candidates-per-item", type=int, default=3)
    args = parser.parse_args()

    with open(args.input_csv, newline="") as f:
        rows = list(csv.DictReader(f))

    api = keepa.Keepa(config.KEEPA_API_KEY, timeout=90.0)
    api.update_status()
    tokens_before = api.tokens_left
    print(f"Tokens left before run: {tokens_before}")

    print(f"Searching {len(rows)} catalog items via Product Finder...")
    row_candidates: list[tuple[dict, str, list[str]]] = []
    all_asins: set[str] = set()
    for idx, row in enumerate(rows):
        title_query = build_search_title(row.get("Description", ""))
        candidates = find_candidates(api, title_query, n=args.candidates_per_item)
        row_candidates.append((row, title_query, candidates))
        all_asins.update(candidates)
        if (idx + 1) % 25 == 0:
            print(f"  searched {idx + 1}/{len(rows)}, {len(all_asins)} unique candidate ASINs so far")

    api.update_status()
    tokens_after_search = api.tokens_left
    print(f"Tokens left after Product Finder phase: {tokens_after_search} "
          f"(used {tokens_before - tokens_after_search} for {len(rows)} searches)")

    print(f"Total unique candidate ASINs to fetch stats for: {len(all_asins)}")

    asin_data: dict[str, dict] = {}
    asin_list = list(all_asins)
    batch_size = config.KEEPA_INVOICE_BATCH_SIZE
    for i in range(0, len(asin_list), batch_size):
        chunk = asin_list[i:i + batch_size]
        api.update_status()
        if api.tokens_left - len(chunk) < config.KEEPA_TOKEN_RESERVE:
            wait_s = api.time_to_refill
            print(f"  pausing {wait_s:.0f}s to keep {config.KEEPA_TOKEN_RESERVE} tokens in reserve")
            time.sleep(wait_s)
        try:
            # history=True is required here (unlike the UPC pipeline) --
            # Amazon Present % is computed from csv[0] (Amazon price
            # history), which Keepa omits entirely when history=False.
            # Confirmed via the test batch: every match came back 0.0%
            # even when Amazon held the buy box, which is the tell that
            # csv data was simply missing, not that Amazon was truly absent.
            products = api.query(chunk, stats=90, offers=20, history=True, buybox=True, wait=True)
        except Exception as exc:
            print(f"  stats query failed for chunk starting at {i}: {exc}")
            time.sleep(5)
            continue
        for p in products:
            rec = parse_product(p)
            if rec["asin"]:
                asin_data[rec["asin"]] = rec
        print(f"  fetched stats {min(i + batch_size, len(asin_list))}/{len(asin_list)}")

    with open(args.csv_out, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow([
            "ItemCode", "Description", "CasePack", "Source", "Search Query",
            "Best ASIN", "Matched Title", "BSR", "Monthly Sold", "Seller Count",
            "Amazon Present %", "Amazon Is Buybox", "Category",
        ])
        for row, title_query, candidates in row_candidates:
            best = None
            for asin in candidates:
                rec = asin_data.get(asin)
                if not rec:
                    continue
                if best is None:
                    best = rec
                    continue
                # prefer higher monthly sold; fall back to better (lower) BSR
                if rec["monthly_sold"] != best["monthly_sold"]:
                    if rec["monthly_sold"] > best["monthly_sold"]:
                        best = rec
                elif best["bsr"] == 0 or (rec["bsr"] and rec["bsr"] < best["bsr"]):
                    best = rec

            w.writerow([
                row.get("ItemCode", ""), row.get("Description", ""),
                row.get("CasePack", ""), row.get("Source", ""), title_query,
                best["asin"] if best else "",
                best["title"] if best else "",
                best["bsr"] if best else "",
                best["monthly_sold"] if best else "",
                best["seller_count"] if best else "",
                best["amazon_pct"] if best else "",
                best["amazon_is_buybox"] if best else "",
                best["category"] if best else "",
            ])

    print("Wrote", args.csv_out)


if __name__ == "__main__":
    main()
