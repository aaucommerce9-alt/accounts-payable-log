"""FBA/FBM profitability calculator for invoice-sourced SKUs.

Profit = sell_price − referral_fee − fulfillment_fee − total_cost_per_unit
  FBA fulfillment_fee = Keepa pick-and-pack fee (fallback: weight-tier estimate)
  FBM fulfillment_fee = outbound shipping (weight-tier estimate) + packaging
"""
from . import config
from .models import AsinRecord, InvoiceLineItem, SkuEvaluation


def evaluate_sku(item: InvoiceLineItem, asin: AsinRecord, channel: str) -> SkuEvaluation:
    channel = channel.upper()
    if channel not in ("FBA", "FBM"):
        raise ValueError(f"Unknown channel: {channel}")

    sell_price = asin.price_usd
    referral_fee = _referral_fee(sell_price, asin.category)

    total_cost = item.cost_per_unit + config.PREP_COST_USD
    if channel == "FBA":
        fulfillment_fee = asin.fba_fee_usd or _tiered_fee(asin.weight_lb, config.FBA_FEE_WEIGHT_TIERS)
        total_cost += config.INBOUND_SHIPPING_PER_UNIT
    else:
        fulfillment_fee = _tiered_fee(asin.weight_lb, config.SHIPPING_WEIGHT_TIERS) + config.PACKAGING_COST_USD

    profit = sell_price - referral_fee - fulfillment_fee - total_cost
    margin_pct = (profit / sell_price * 100) if sell_price > 0 else 0.0
    roi_pct = (profit / total_cost * 100) if total_cost > 0 else 0.0

    verdict, reasons = _verdict(
        margin_pct, roi_pct, asin.units_per_month, asin.bsr, asin.amazon_is_buybox
    )

    return SkuEvaluation(
        upc=item.upc,
        asin=asin.asin,
        description=item.description or asin.title,
        cost_per_unit=item.cost_per_unit,
        quantity=item.quantity,
        sell_price=sell_price,
        channel=channel,
        referral_fee=round(referral_fee, 2),
        fulfillment_fee=round(fulfillment_fee, 2),
        total_cost_per_unit=round(total_cost, 2),
        profit_per_unit=round(profit, 2),
        margin_pct=round(margin_pct, 1),
        roi_pct=round(roi_pct, 1),
        units_per_month=asin.units_per_month,
        seller_count=asin.seller_count,
        amazon_present_pct=asin.amazon_present_pct,
        bsr=asin.bsr,
        amazon_is_buybox=asin.amazon_is_buybox,
        verdict=verdict,
        reasons=reasons,
    )


def _referral_fee(sell_price: float, category: str) -> float:
    rate = config.CATEGORY_REFERRAL_FEE_PCT.get(category, config.DEFAULT_REFERRAL_FEE_PCT)
    fee = sell_price * rate / 100
    return max(fee, config.MIN_REFERRAL_FEE_USD)


def _tiered_fee(weight_lb: float, tiers: list[tuple[float, float]]) -> float:
    for max_weight, fee in tiers:
        if weight_lb <= max_weight:
            return fee
    return tiers[-1][1]


def _verdict(
    margin_pct: float, roi_pct: float, units_per_month: int, bsr: int, amazon_is_buybox: bool
) -> tuple[str, list[str]]:
    if config.EXCLUDE_AMAZON_BUYBOX and amazon_is_buybox:
        return "skip", ["amazon_has_buybox"]

    reasons = []
    if margin_pct < config.MIN_SKU_MARGIN_PCT:
        reasons.append(f"margin={margin_pct:.1f}%")
    if roi_pct < config.MIN_SKU_ROI_PCT:
        reasons.append(f"roi={roi_pct:.1f}%")
    if units_per_month < config.MIN_SKU_VELOCITY:
        reasons.append(f"units/mo={units_per_month}")
    if bsr <= 0 or bsr > config.MAX_SKU_BSR:
        reasons.append(f"bsr={bsr or 'unknown'}")

    if not reasons:
        return "buy", []
    if margin_pct > 0 and roi_pct > 0:
        return "marginal", reasons
    return "skip", reasons
