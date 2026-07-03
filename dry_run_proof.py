#!/usr/bin/env python3
"""
Dry-run proof script:
  - Generates 3 personalized emails from mock brand data (no Keepa)
  - Writes one row to the Google Sheet (no send)
  - Prints everything
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
load_dotenv()

from datetime import date
from swiftcart.models import BrandRecord
from swiftcart.email_writer import personalize_email
from swiftcart.sheets_client import ensure_header, upsert_brand

MOCK_BRANDS = [
    BrandRecord(
        name="NaturePure Wellness",
        parent="NaturePure Wellness",
        domain="naturepurewellness.com",
        est_monthly_revenue=180_000,
        avg_sellers=4.2,
        amazon_present_pct=8.0,
        qualifying_asins=6,
        units_per_month=2_800,
        score=8.21,
        contact_email="wholesale@naturepurewellness.com",
        categories=["Vitamins & Supplements", "Health & Wellness"],
    ),
    BrandRecord(
        name="PetHaven Supplies",
        parent="PetHaven Supplies",
        domain="pethavensupplies.com",
        est_monthly_revenue=95_000,
        avg_sellers=5.0,
        amazon_present_pct=12.0,
        qualifying_asins=3,
        units_per_month=1_400,
        score=7.54,
        contact_email="info@pethavensupplies.com",
        categories=["Pet Supplies", "Dog Accessories"],
    ),
    BrandRecord(
        name="CleanCraft Tools",
        parent="CleanCraft Tools",
        domain="cleancrafttools.com",
        est_monthly_revenue=310_000,
        avg_sellers=6.5,
        amazon_present_pct=5.0,
        qualifying_asins=11,
        units_per_month=4_100,
        score=8.89,
        contact_email="sales@cleancrafttools.com",
        categories=["Cleaning Supplies", "Commercial Cleaning"],
    ),
]

def main():
    print("=" * 60)
    print("DRY RUN — no emails sent, no Keepa used")
    print("=" * 60)

    print("\n--- MOCK BRANDS ---")
    for b in MOCK_BRANDS:
        print(f"  {b.name} | rev=${b.est_monthly_revenue:,.0f} | score={b.score} | to={b.contact_email}")

    print("\n--- GENERATED EMAILS ---\n")
    emails = []
    for b in MOCK_BRANDS:
        subject, body = personalize_email(b, followup_num=0)
        emails.append((subject, body))
        print(f"TO:      {b.contact_email}")
        print(f"SUBJECT: {subject}")
        print("-" * 50)
        print(body)
        print("=" * 60 + "\n")

    print("--- SHEET WRITE (first brand only) ---")
    first = MOCK_BRANDS[0]
    first.email_status = "queued"
    first.send_date = None
    ensure_header()
    upsert_brand(first)
    print(f"  Row written for: {first.name}")
    print(f"  Columns: Brand | Parent | Domain | Revenue | Avg sellers | Amazon% | ASINs | Units | Score | Email | Status | ...")
    print(f"  Values:  {first.name} | {first.parent} | {first.domain} | "
          f"${first.est_monthly_revenue:,.0f} | {first.avg_sellers} | {first.amazon_present_pct}% | "
          f"{first.qualifying_asins} | {first.units_per_month} | {first.score} | "
          f"{first.contact_email} | {first.email_status}")

    print("\n✓ Dry run complete — nothing sent, no Keepa tokens used.")

if __name__ == "__main__":
    main()
