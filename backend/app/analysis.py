"""
Fee, grade, and risk analysis for marketplace product listings.
All values USD unless noted.
"""
from dataclasses import dataclass
from typing import Literal

REFERRAL_RATES = {
    "Electronics": 0.08,
    "Clothing": 0.17,
    "Home & Kitchen": 0.15,
    "Toys": 0.15,
    "Books": 0.15,
    "Health": 0.08,
    "Sports": 0.15,
    "Automotive": 0.12,
    "Other": 0.15,
}


@dataclass
class FeeBreakdown:
    referral_fee: float
    fulfillment_fee: float
    storage_fee: float
    total_fees: float
    net_revenue: float
    margin_pct: float


@dataclass
class GradeResult:
    grade: Literal["A", "B", "C", "D", "F"]
    score: float  # 0-100
    reasons: list[str]


@dataclass
class RiskFlag:
    level: Literal["low", "medium", "high"]
    label: str
    detail: str


@dataclass
class AnalysisResult:
    fees: FeeBreakdown
    grade: GradeResult
    risks: list[RiskFlag]
    recommendation: str


def calculate_fees(price, cost, category, weight_lbs, monthly_units) -> FeeBreakdown:
    referral_fee = price * REFERRAL_RATES.get(category, 0.15)

    if weight_lbs <= 1:
        fulfillment_fee = 3.22
    elif weight_lbs <= 2:
        fulfillment_fee = 4.75
    elif weight_lbs <= 3:
        fulfillment_fee = 5.40
    else:
        fulfillment_fee = 5.40 + (weight_lbs - 3) * 0.38

    storage_fee = (weight_lbs / 166) * 0.75 * monthly_units

    total_fees = referral_fee + fulfillment_fee + storage_fee
    net_revenue = price - cost - total_fees
    margin_pct = (net_revenue / price) * 100 if price > 0 else 0

    return FeeBreakdown(
        referral_fee=round(referral_fee, 4),
        fulfillment_fee=round(fulfillment_fee, 4),
        storage_fee=round(storage_fee, 4),
        total_fees=round(total_fees, 4),
        net_revenue=round(net_revenue, 4),
        margin_pct=round(margin_pct, 4),
    )


def grade_product(fees: FeeBreakdown, review_count, review_rating, monthly_units) -> GradeResult:
    score = 100
    reasons = []

    if fees.margin_pct < 15:
        score -= 30
        reasons.append("Margin below 15% — very low profitability")
    elif fees.margin_pct < 25:
        score -= 15
        reasons.append("Margin below 25% — moderate profitability concern")

    if review_rating < 3.5:
        score -= 20
        reasons.append("Review rating below 3.5 — poor customer satisfaction")
    elif review_rating < 4.0:
        score -= 10
        reasons.append("Review rating below 4.0 — below average satisfaction")

    if review_count < 10:
        score -= 15
        reasons.append("Fewer than 10 reviews — very low social proof")
    elif review_count < 50:
        score -= 5
        reasons.append("Fewer than 50 reviews — limited social proof")

    if monthly_units < 10:
        score -= 10
        reasons.append("Fewer than 10 monthly units — very low sales velocity")
    elif monthly_units < 30:
        score -= 5
        reasons.append("Fewer than 30 monthly units — low sales velocity")

    score = max(0, min(100, score))

    if score >= 85:
        grade = "A"
    elif score >= 70:
        grade = "B"
    elif score >= 55:
        grade = "C"
    elif score >= 40:
        grade = "D"
    else:
        grade = "F"

    return GradeResult(grade=grade, score=score, reasons=reasons)


def assess_risks(fees: FeeBreakdown, price, weight_lbs, review_count, review_rating, category) -> list[RiskFlag]:
    risks = []

    if fees.margin_pct < 10:
        risks.append(RiskFlag(
            level="high",
            label="Negative/minimal margin",
            detail=f"Margin is {fees.margin_pct:.1f}% — barely covers costs or is negative",
        ))

    if weight_lbs > 50:
        risks.append(RiskFlag(
            level="high",
            label="Oversized shipping costs",
            detail=f"Item weighs {weight_lbs} lbs — oversized fulfillment fees significantly impact margins",
        ))

    if fees.margin_pct < 20:
        risks.append(RiskFlag(
            level="medium",
            label="Thin margin",
            detail=f"Margin is {fees.margin_pct:.1f}% — leaves little room for returns, ads, or price drops",
        ))

    if review_rating < 3.5:
        risks.append(RiskFlag(
            level="medium",
            label="Poor reviews",
            detail=f"Rating of {review_rating} — poor reviews reduce conversion and may trigger suppression",
        ))

    if price < 15:
        risks.append(RiskFlag(
            level="medium",
            label="Low price point — fees eat margin",
            detail=f"Price of ${price:.2f} — fixed fulfillment fees consume a large percentage at low price points",
        ))

    if review_count < 20:
        risks.append(RiskFlag(
            level="low",
            label="Low review count — social proof risk",
            detail=f"Only {review_count} reviews — low review count reduces buyer confidence",
        ))

    if category == "Electronics":
        risks.append(RiskFlag(
            level="low",
            label="Electronics return rate risk",
            detail="Electronics category has above-average return rates which can erode margins",
        ))

    return risks


def analyze(price, cost, category, weight_lbs, monthly_units, review_count, review_rating) -> AnalysisResult:
    fees = calculate_fees(price, cost, category, weight_lbs, monthly_units)
    grade = grade_product(fees, review_count, review_rating, monthly_units)
    risks = assess_risks(fees, price, weight_lbs, review_count, review_rating, category)

    if grade.grade in ("A", "B"):
        recommendation = "Strong candidate — proceed"
    elif grade.grade == "C":
        recommendation = "Borderline — address risks before listing"
    else:
        recommendation = "Not recommended — rework pricing or sourcing"

    return AnalysisResult(fees=fees, grade=grade, risks=risks, recommendation=recommendation)
