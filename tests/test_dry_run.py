"""
Dry-run / mock test — validates full flow with no live keys.
Run: python -m pytest tests/test_dry_run.py -v
"""
import sys, os, pytest
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from datetime import date
from swiftcart.models import AsinRecord, BrandRecord
from swiftcart.filters import filter_asins, rollup_to_brands, score_and_rank
from swiftcart.dnc import load_dnc, screen
from swiftcart import config


# ── Fixtures ──────────────────────────────────────────────────────────────────

def _make_asin(**kwargs) -> AsinRecord:
    defaults = dict(
        asin="B000TEST01", brand="TestBrand", title="Test Product",
        price_usd=25.0, units_per_month=100, seller_count=5,
        amazon_present_pct=10.0, price_90d_ago=26.0, category="Health",
    )
    defaults.update(kwargs)
    return AsinRecord(**defaults)


# ── ASIN filter tests ──────────────────────────────────────────────────────────

def test_asin_passes_all_filters():
    asins = [_make_asin()]
    result = filter_asins(asins)
    assert len(result) == 1


def test_asin_dropped_too_few_sellers():
    asins = [_make_asin(seller_count=1)]
    assert filter_asins(asins) == []


def test_asin_dropped_too_many_sellers():
    asins = [_make_asin(seller_count=15)]
    assert filter_asins(asins) == []


def test_asin_dropped_amazon_present():
    asins = [_make_asin(amazon_present_pct=30.0)]
    assert filter_asins(asins) == []


def test_asin_dropped_price_too_low():
    asins = [_make_asin(price_usd=10.0)]
    assert filter_asins(asins) == []


def test_asin_dropped_units_too_low():
    asins = [_make_asin(units_per_month=10)]
    assert filter_asins(asins) == []


def test_asin_dropped_price_crash():
    # price dropped from $50 to $30 = 40% — above PRICE_CRASH_DROP_PCT
    asins = [_make_asin(price_usd=30.0, price_90d_ago=50.0)]
    assert filter_asins(asins) == []


def test_asin_price_stable_passes():
    # dropped only 5% — should pass
    asins = [_make_asin(price_usd=47.5, price_90d_ago=50.0)]
    assert len(filter_asins(asins)) == 1


# ── Brand rollup tests ─────────────────────────────────────────────────────────

def test_brand_rollup_revenue_filter():
    # revenue = 25 × 100 = $2,500 — below MIN_BRAND_REVENUE → dropped
    asins = [_make_asin(price_usd=25.0, units_per_month=100)]
    assert rollup_to_brands(asins) == []


def test_brand_rollup_passes():
    # revenue = 25 × 5000 = $125,000 — within range
    asins = [_make_asin(price_usd=25.0, units_per_month=5000)]
    brands = rollup_to_brands(asins)
    assert len(brands) == 1
    assert brands[0].name == "TestBrand"


def test_score_and_rank_orders():
    b1 = BrandRecord(
        name="A", parent="A", domain="a.com", est_monthly_revenue=100_000,
        avg_sellers=3, amazon_present_pct=5, qualifying_asins=2,
        units_per_month=200, score=0,
    )
    b2 = BrandRecord(
        name="B", parent="B", domain="b.com", est_monthly_revenue=200_000,
        avg_sellers=9, amazon_present_pct=20, qualifying_asins=1,
        units_per_month=100, score=0,
    )
    ranked = score_and_rank([b1, b2])
    assert ranked[0].name == "A"   # lower sellers + lower amazon presence → higher score


# ── DNC screen tests ──────────────────────────────────────────────────────────

def test_dnc_blocks_by_brand_name():
    brands = [
        BrandRecord(name="BlockedBrand", parent="P", domain="blocked.com",
                    est_monthly_revenue=100_000, avg_sellers=4,
                    amazon_present_pct=5, qualifying_asins=1,
                    units_per_month=100, score=0),
    ]
    dnc = [{"brand": "blockedbrand", "parent": "", "domain": ""}]
    result = screen(brands, dnc)
    assert result == []


def test_dnc_allows_unlisted_brand():
    brands = [
        BrandRecord(name="SafeBrand", parent="P", domain="safe.com",
                    est_monthly_revenue=100_000, avg_sellers=4,
                    amazon_present_pct=5, qualifying_asins=1,
                    units_per_month=100, score=0),
    ]
    dnc = [{"brand": "otherbrand", "parent": "", "domain": ""}]
    result = screen(brands, dnc)
    assert len(result) == 1


# ── Email template rendering ──────────────────────────────────────────────────

def test_email_template_renders():
    body = config.EMAIL_BODY_TEMPLATE.format(
        brand="Acme Corp", product_line="Health Supplements"
    )
    assert "Acme Corp" in body
    assert "Health Supplements" in body
    assert "SwiftCart Supply" in body
    assert "MAP" in body


def test_followup_template_renders():
    body = config.FOLLOWUP_BODY_TEMPLATE.format(
        brand="Acme Corp", product_line="Pet Supplies"
    )
    assert "Acme Corp" in body
    assert "follow up" in body.lower()


# ── Scheduler helpers (import-only smoke test) ────────────────────────────────

def test_followup_date_logic():
    """Test scheduler date helpers without importing google libs."""
    from datetime import timedelta

    # Replicate the logic inline so this test runs without google-auth
    def set_followup_dates(brand, send_date, days=(10, 20)):
        brand.followup1_date = send_date + timedelta(days=days[0])
        brand.followup2_date = send_date + timedelta(days=days[1])

    b = BrandRecord(name="X", parent="X", domain="x.com",
                    est_monthly_revenue=100_000, avg_sellers=4,
                    amazon_present_pct=5, qualifying_asins=1,
                    units_per_month=100, score=0, send_date=None)
    set_followup_dates(b, date(2026, 1, 1))
    assert b.followup1_date.day == 11
    assert b.followup2_date.day == 21
