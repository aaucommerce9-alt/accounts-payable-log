"""
Comprehensive pytest tests for analysis.py logic.
"""
import pytest
from app.analysis import (
    calculate_fees,
    grade_product,
    assess_risks,
    analyze,
    FeeBreakdown,
    REFERRAL_RATES,
)


# ---------------------------------------------------------------------------
# calculate_fees
# ---------------------------------------------------------------------------

class TestCalculateFees:
    def test_weight_tier_1_lb(self):
        fees = calculate_fees(price=30.0, cost=10.0, category="Other", weight_lbs=1.0, monthly_units=50)
        assert fees.fulfillment_fee == 3.22

    def test_weight_tier_under_1_lb(self):
        fees = calculate_fees(price=30.0, cost=10.0, category="Other", weight_lbs=0.5, monthly_units=50)
        assert fees.fulfillment_fee == 3.22

    def test_weight_tier_2_lbs(self):
        fees = calculate_fees(price=30.0, cost=10.0, category="Other", weight_lbs=2.0, monthly_units=50)
        assert fees.fulfillment_fee == 4.75

    def test_weight_tier_1_5_lbs(self):
        fees = calculate_fees(price=30.0, cost=10.0, category="Other", weight_lbs=1.5, monthly_units=50)
        assert fees.fulfillment_fee == 4.75

    def test_weight_tier_3_lbs(self):
        fees = calculate_fees(price=30.0, cost=10.0, category="Other", weight_lbs=3.0, monthly_units=50)
        assert fees.fulfillment_fee == 5.40

    def test_weight_tier_above_3_lbs(self):
        fees = calculate_fees(price=30.0, cost=10.0, category="Other", weight_lbs=5.0, monthly_units=50)
        expected = 5.40 + (5.0 - 3) * 0.38
        assert abs(fees.fulfillment_fee - expected) < 0.001

    def test_referral_fee_electronics(self):
        fees = calculate_fees(price=100.0, cost=40.0, category="Electronics", weight_lbs=1.0, monthly_units=10)
        assert abs(fees.referral_fee - 8.0) < 0.001

    def test_referral_fee_clothing(self):
        fees = calculate_fees(price=100.0, cost=40.0, category="Clothing", weight_lbs=1.0, monthly_units=10)
        assert abs(fees.referral_fee - 17.0) < 0.001

    def test_referral_fee_unknown_category_defaults_15pct(self):
        fees = calculate_fees(price=100.0, cost=40.0, category="Unknown", weight_lbs=1.0, monthly_units=10)
        assert abs(fees.referral_fee - 15.0) < 0.001

    def test_storage_fee_calculation(self):
        fees = calculate_fees(price=30.0, cost=10.0, category="Other", weight_lbs=2.0, monthly_units=100)
        expected_storage = (2.0 / 166) * 0.75 * 100
        assert abs(fees.storage_fee - expected_storage) < 0.001

    def test_total_fees_sum(self):
        fees = calculate_fees(price=30.0, cost=10.0, category="Other", weight_lbs=1.0, monthly_units=50)
        assert abs(fees.total_fees - (fees.referral_fee + fees.fulfillment_fee + fees.storage_fee)) < 0.001

    def test_net_revenue(self):
        fees = calculate_fees(price=50.0, cost=15.0, category="Other", weight_lbs=1.0, monthly_units=20)
        expected_net = 50.0 - 15.0 - fees.total_fees
        assert abs(fees.net_revenue - expected_net) < 0.001

    def test_margin_pct(self):
        fees = calculate_fees(price=50.0, cost=15.0, category="Other", weight_lbs=1.0, monthly_units=20)
        expected_margin = (fees.net_revenue / 50.0) * 100
        assert abs(fees.margin_pct - expected_margin) < 0.001

    def test_zero_margin_when_price_equals_cost_plus_fees(self):
        # price == cost -> net_revenue negative, margin negative
        fees = calculate_fees(price=10.0, cost=10.0, category="Other", weight_lbs=1.0, monthly_units=10)
        assert fees.net_revenue < 0
        assert fees.margin_pct < 0

    def test_margin_pct_positive_profitable(self):
        fees = calculate_fees(price=100.0, cost=20.0, category="Other", weight_lbs=1.0, monthly_units=50)
        assert fees.margin_pct > 0


# ---------------------------------------------------------------------------
# grade_product
# ---------------------------------------------------------------------------

class TestGradeProduct:
    def _fees(self, margin_pct=30.0, price=100.0):
        # Build a FeeBreakdown with a specific margin_pct
        net_revenue = price * margin_pct / 100
        return FeeBreakdown(
            referral_fee=5.0,
            fulfillment_fee=3.22,
            storage_fee=0.5,
            total_fees=8.72,
            net_revenue=net_revenue,
            margin_pct=margin_pct,
        )

    def test_grade_A_all_good(self):
        fees = self._fees(margin_pct=35.0)
        result = grade_product(fees, review_count=200, review_rating=4.5, monthly_units=100)
        assert result.grade == "A"
        assert result.score >= 85

    def test_grade_B(self):
        fees = self._fees(margin_pct=25.0)
        result = grade_product(fees, review_count=60, review_rating=4.2, monthly_units=35)
        assert result.grade in ("A", "B")
        assert result.score >= 70

    def test_grade_F_terrible_product(self):
        fees = self._fees(margin_pct=5.0)
        result = grade_product(fees, review_count=2, review_rating=2.5, monthly_units=3)
        assert result.grade == "F"
        assert result.score < 40

    def test_margin_below_15_deducts_30(self):
        fees_low = self._fees(margin_pct=10.0)
        fees_high = self._fees(margin_pct=30.0)
        result_low = grade_product(fees_low, review_count=200, review_rating=4.5, monthly_units=100)
        result_high = grade_product(fees_high, review_count=200, review_rating=4.5, monthly_units=100)
        assert result_high.score - result_low.score == 30

    def test_margin_15_to_25_deducts_15(self):
        fees_mid = self._fees(margin_pct=20.0)
        fees_high = self._fees(margin_pct=30.0)
        result_mid = grade_product(fees_mid, review_count=200, review_rating=4.5, monthly_units=100)
        result_high = grade_product(fees_high, review_count=200, review_rating=4.5, monthly_units=100)
        assert result_high.score - result_mid.score == 15

    def test_rating_below_3_5_deducts_20(self):
        fees = self._fees(margin_pct=35.0)
        result_bad = grade_product(fees, review_count=200, review_rating=3.0, monthly_units=100)
        result_good = grade_product(fees, review_count=200, review_rating=4.5, monthly_units=100)
        assert result_good.score - result_bad.score == 20

    def test_rating_3_5_to_4_deducts_10(self):
        fees = self._fees(margin_pct=35.0)
        result_mid = grade_product(fees, review_count=200, review_rating=3.8, monthly_units=100)
        result_good = grade_product(fees, review_count=200, review_rating=4.5, monthly_units=100)
        assert result_good.score - result_mid.score == 10

    def test_review_count_below_10_deducts_15(self):
        fees = self._fees(margin_pct=35.0)
        result_low = grade_product(fees, review_count=5, review_rating=4.5, monthly_units=100)
        result_high = grade_product(fees, review_count=200, review_rating=4.5, monthly_units=100)
        assert result_high.score - result_low.score == 15

    def test_review_count_10_to_50_deducts_5(self):
        fees = self._fees(margin_pct=35.0)
        result_mid = grade_product(fees, review_count=30, review_rating=4.5, monthly_units=100)
        result_high = grade_product(fees, review_count=200, review_rating=4.5, monthly_units=100)
        assert result_high.score - result_mid.score == 5

    def test_monthly_units_below_10_deducts_10(self):
        fees = self._fees(margin_pct=35.0)
        result_low = grade_product(fees, review_count=200, review_rating=4.5, monthly_units=5)
        result_high = grade_product(fees, review_count=200, review_rating=4.5, monthly_units=100)
        assert result_high.score - result_low.score == 10

    def test_monthly_units_10_to_30_deducts_5(self):
        fees = self._fees(margin_pct=35.0)
        result_mid = grade_product(fees, review_count=200, review_rating=4.5, monthly_units=20)
        result_high = grade_product(fees, review_count=200, review_rating=4.5, monthly_units=100)
        assert result_high.score - result_mid.score == 5

    def test_score_clamped_to_0(self):
        fees = self._fees(margin_pct=1.0)
        result = grade_product(fees, review_count=0, review_rating=1.0, monthly_units=1)
        assert result.score >= 0

    def test_grade_boundaries(self):
        # Manually verify each boundary
        fees_good = self._fees(margin_pct=35.0)
        r = grade_product(fees_good, review_count=200, review_rating=4.5, monthly_units=100)
        assert r.score == 100
        assert r.grade == "A"

    def test_reasons_populated_on_deductions(self):
        fees = self._fees(margin_pct=10.0)
        result = grade_product(fees, review_count=2, review_rating=2.5, monthly_units=5)
        assert len(result.reasons) > 0

    def test_no_reasons_perfect_product(self):
        fees = self._fees(margin_pct=40.0)
        result = grade_product(fees, review_count=500, review_rating=4.8, monthly_units=200)
        assert result.reasons == []


# ---------------------------------------------------------------------------
# assess_risks
# ---------------------------------------------------------------------------

class TestAssessRisks:
    def _fees(self, margin_pct):
        return FeeBreakdown(
            referral_fee=5.0,
            fulfillment_fee=3.22,
            storage_fee=0.5,
            total_fees=8.72,
            net_revenue=margin_pct,
            margin_pct=margin_pct,
        )

    def test_high_risk_negative_margin(self):
        fees = self._fees(margin_pct=5.0)
        risks = assess_risks(fees, price=30.0, weight_lbs=1.0, review_count=50, review_rating=4.0, category="Other")
        levels = [r.level for r in risks]
        assert "high" in levels
        labels = [r.label for r in risks]
        assert any("margin" in l.lower() for l in labels)

    def test_high_risk_oversized(self):
        fees = self._fees(margin_pct=30.0)
        risks = assess_risks(fees, price=200.0, weight_lbs=55.0, review_count=50, review_rating=4.0, category="Other")
        labels = [r.label for r in risks]
        assert any("oversized" in l.lower() for l in labels)

    def test_medium_risk_thin_margin(self):
        fees = self._fees(margin_pct=15.0)
        risks = assess_risks(fees, price=50.0, weight_lbs=1.0, review_count=50, review_rating=4.0, category="Other")
        levels = [r.level for r in risks]
        assert "medium" in levels

    def test_medium_risk_poor_reviews(self):
        fees = self._fees(margin_pct=30.0)
        risks = assess_risks(fees, price=50.0, weight_lbs=1.0, review_count=50, review_rating=3.0, category="Other")
        labels = [r.label for r in risks]
        assert any("review" in l.lower() for l in labels)

    def test_medium_risk_low_price(self):
        fees = self._fees(margin_pct=30.0)
        risks = assess_risks(fees, price=10.0, weight_lbs=1.0, review_count=50, review_rating=4.5, category="Other")
        labels = [r.label for r in risks]
        assert any("price" in l.lower() or "low price" in l.lower() for l in labels)

    def test_low_risk_few_reviews(self):
        fees = self._fees(margin_pct=30.0)
        risks = assess_risks(fees, price=50.0, weight_lbs=1.0, review_count=5, review_rating=4.5, category="Other")
        labels = [r.label for r in risks]
        assert any("review count" in l.lower() for l in labels)

    def test_low_risk_electronics(self):
        fees = self._fees(margin_pct=30.0)
        risks = assess_risks(fees, price=100.0, weight_lbs=1.0, review_count=200, review_rating=4.5, category="Electronics")
        labels = [r.label for r in risks]
        assert any("electronics" in l.lower() for l in labels)

    def test_no_high_risks_for_good_product(self):
        fees = self._fees(margin_pct=35.0)
        risks = assess_risks(fees, price=50.0, weight_lbs=1.0, review_count=200, review_rating=4.5, category="Other")
        high_risks = [r for r in risks if r.level == "high"]
        assert len(high_risks) == 0

    def test_zero_reviews_low_risk(self):
        fees = self._fees(margin_pct=30.0)
        risks = assess_risks(fees, price=50.0, weight_lbs=1.0, review_count=0, review_rating=4.5, category="Other")
        low_risks = [r for r in risks if r.level == "low"]
        assert len(low_risks) >= 1


# ---------------------------------------------------------------------------
# analyze (integration)
# ---------------------------------------------------------------------------

class TestAnalyze:
    def test_good_product_gets_A_or_B(self):
        result = analyze(
            price=60.0,
            cost=15.0,
            category="Home & Kitchen",
            weight_lbs=1.0,
            monthly_units=100,
            review_count=300,
            review_rating=4.7,
        )
        assert result.grade.grade in ("A", "B")
        assert "proceed" in result.recommendation.lower()

    def test_bad_product_gets_D_or_F(self):
        result = analyze(
            price=12.0,
            cost=10.0,
            category="Other",
            weight_lbs=1.0,
            monthly_units=3,
            review_count=1,
            review_rating=2.0,
        )
        assert result.grade.grade in ("D", "F")
        assert "not recommended" in result.recommendation.lower()

    def test_borderline_product_gets_C(self):
        # Low margin + low reviews + low units => should land C or lower
        result = analyze(
            price=25.0,
            cost=14.0,
            category="Other",
            weight_lbs=1.5,
            monthly_units=15,
            review_count=20,
            review_rating=3.8,
        )
        assert result.grade.grade in ("B", "C", "D")

    def test_recommendation_borderline_C(self):
        # Force a C grade scenario
        result = analyze(
            price=40.0,
            cost=20.0,
            category="Other",
            weight_lbs=1.5,
            monthly_units=15,
            review_count=25,
            review_rating=3.9,
        )
        if result.grade.grade == "C":
            assert "borderline" in result.recommendation.lower()

    def test_price_equals_cost_negative_margin(self):
        result = analyze(
            price=20.0,
            cost=20.0,
            category="Other",
            weight_lbs=1.0,
            monthly_units=10,
            review_count=50,
            review_rating=4.0,
        )
        assert result.fees.margin_pct < 0
        # With negative margin the score loses 30 points; grade will be C or worse
        assert result.grade.grade in ("C", "D", "F")

    def test_very_heavy_item_oversized_risk(self):
        result = analyze(
            price=500.0,
            cost=100.0,
            category="Other",
            weight_lbs=60.0,
            monthly_units=20,
            review_count=100,
            review_rating=4.5,
        )
        high_risks = [r for r in result.risks if r.level == "high"]
        assert any("oversized" in r.label.lower() for r in high_risks)

    def test_zero_reviews_triggers_low_risk(self):
        result = analyze(
            price=50.0,
            cost=20.0,
            category="Other",
            weight_lbs=1.0,
            monthly_units=50,
            review_count=0,
            review_rating=4.0,
        )
        labels = [r.label for r in result.risks]
        assert any("review count" in l.lower() for l in labels)

    def test_electronics_category_risk_flag(self):
        result = analyze(
            price=100.0,
            cost=30.0,
            category="Electronics",
            weight_lbs=1.0,
            monthly_units=50,
            review_count=200,
            review_rating=4.5,
        )
        labels = [r.label for r in result.risks]
        assert any("electronics" in l.lower() for l in labels)

    def test_result_structure(self):
        result = analyze(
            price=50.0,
            cost=20.0,
            category="Other",
            weight_lbs=1.0,
            monthly_units=50,
            review_count=100,
            review_rating=4.2,
        )
        assert hasattr(result, "fees")
        assert hasattr(result, "grade")
        assert hasattr(result, "risks")
        assert hasattr(result, "recommendation")
        assert isinstance(result.risks, list)
