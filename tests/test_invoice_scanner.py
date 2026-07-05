"""Tests for invoice parsing and FBA/FBM profitability calculation."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from swiftcart.invoice_parser import parse_invoice
from swiftcart.models import AsinRecord, InvoiceLineItem
from swiftcart.profit_calculator import evaluate_sku
from swiftcart import config


# ── Invoice parsing ────────────────────────────────────────────────────────────

def test_parse_csv_invoice(tmp_path):
    csv_path = tmp_path / "invoice.csv"
    csv_path.write_text(
        "UPC,Description,Unit Cost,Qty\n"
        "012345678905,Widget A,4.50,100\n"
        " 098765432109 ,Widget B,$9.99,50\n"
    )
    items = parse_invoice(str(csv_path))
    assert len(items) == 2
    assert items[0].upc == "012345678905"
    assert items[0].cost_per_unit == 4.50
    assert items[0].quantity == 100
    assert items[1].upc == "098765432109"
    assert items[1].cost_per_unit == 9.99


def test_parse_csv_skips_rows_without_upc(tmp_path):
    csv_path = tmp_path / "invoice.csv"
    csv_path.write_text(
        "UPC,Description,Unit Cost,Qty\n"
        ",Missing UPC,1.00,10\n"
        "012345678905,Widget A,4.50,100\n"
    )
    items = parse_invoice(str(csv_path))
    assert len(items) == 1
    assert items[0].upc == "012345678905"


def test_parse_csv_missing_required_columns_raises(tmp_path):
    csv_path = tmp_path / "invoice.csv"
    csv_path.write_text("Description,Qty\nWidget A,100\n")
    try:
        parse_invoice(str(csv_path))
        assert False, "expected ValueError"
    except ValueError:
        pass


# ── Profit calculator ──────────────────────────────────────────────────────────

def _make_asin(**kwargs) -> AsinRecord:
    defaults = dict(
        asin="B000TEST01", brand="TestBrand", title="Test Product",
        price_usd=30.0, units_per_month=100, seller_count=5,
        amazon_present_pct=10.0, price_90d_ago=30.0, category="Health",
        weight_lb=2.0, fba_fee_usd=0.0,
    )
    defaults.update(kwargs)
    return AsinRecord(**defaults)


def _make_item(**kwargs) -> InvoiceLineItem:
    defaults = dict(upc="012345678905", description="Widget", cost_per_unit=5.0, quantity=10)
    defaults.update(kwargs)
    return InvoiceLineItem(**defaults)


def test_fba_profit_uses_keepa_fee_when_present():
    asin = _make_asin(price_usd=30.0, fba_fee_usd=4.0, category="Unmapped")
    item = _make_item(cost_per_unit=5.0)
    result = evaluate_sku(item, asin, "FBA")

    referral_fee = max(30.0 * config.DEFAULT_REFERRAL_FEE_PCT / 100, config.MIN_REFERRAL_FEE_USD)
    total_cost = 5.0 + config.PREP_COST_USD + config.INBOUND_SHIPPING_PER_UNIT
    expected_profit = 30.0 - referral_fee - 4.0 - total_cost

    assert result.fulfillment_fee == 4.0
    assert result.profit_per_unit == round(expected_profit, 2)
    assert result.channel == "FBA"


def test_fba_falls_back_to_weight_tier_fee_when_keepa_fee_missing():
    asin = _make_asin(price_usd=30.0, fba_fee_usd=0.0, weight_lb=2.0)
    item = _make_item()
    result = evaluate_sku(item, asin, "FBA")
    assert result.fulfillment_fee == 5.50   # 1–3 lb tier


def test_fbm_profit_uses_shipping_tier_plus_packaging():
    asin = _make_asin(price_usd=30.0, weight_lb=0.5)
    item = _make_item(cost_per_unit=5.0)
    result = evaluate_sku(item, asin, "FBM")

    expected_fulfillment = 4.50 + config.PACKAGING_COST_USD   # 0-1 lb tier
    assert result.fulfillment_fee == round(expected_fulfillment, 2)
    assert result.channel == "FBM"


def test_verdict_buy_when_thresholds_met():
    asin = _make_asin(price_usd=50.0, fba_fee_usd=3.0, units_per_month=500)
    item = _make_item(cost_per_unit=5.0)
    result = evaluate_sku(item, asin, "FBA")
    assert result.margin_pct >= config.MIN_SKU_MARGIN_PCT
    assert result.roi_pct >= config.MIN_SKU_ROI_PCT
    assert result.verdict == "buy"


def test_verdict_skip_when_unprofitable():
    asin = _make_asin(price_usd=10.0, fba_fee_usd=3.0, units_per_month=500)
    item = _make_item(cost_per_unit=8.0)
    result = evaluate_sku(item, asin, "FBA")
    assert result.profit_per_unit < 0
    assert result.verdict == "skip"


def test_verdict_marginal_when_profitable_but_under_threshold():
    asin = _make_asin(price_usd=20.0, fba_fee_usd=2.0, units_per_month=500)
    item = _make_item(cost_per_unit=13.0)
    result = evaluate_sku(item, asin, "FBA")
    assert result.profit_per_unit > 0
    assert result.margin_pct < config.MIN_SKU_MARGIN_PCT
    assert result.verdict == "marginal"


def test_invalid_channel_raises():
    asin = _make_asin()
    item = _make_item()
    try:
        evaluate_sku(item, asin, "DTC")
        assert False, "expected ValueError"
    except ValueError:
        pass
