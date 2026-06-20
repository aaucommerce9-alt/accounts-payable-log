"""
Build normalised transaction rows from SP-API Finances API payloads.

Each row is a dict matching the column names in config["excel"]["columns"].
"""

import logging
from datetime import datetime, timezone, date as date_type

logger = logging.getLogger(__name__)

# Transaction types we understand
KNOWN_TYPES = {
    "ShipmentEvent":           "sale",
    "RefundEvent":             "refund",
    "GuaranteeClaimEvent":     "chargeback",
    "ChargebackEvent":         "chargeback",
    "ServiceFeeEvent":         "fee",
    "RemovalShipmentEvent":    "fee",
    "AdjustmentEvent":         "adjustment",
    "CouponPaymentEvent":      "adjustment",
    "ImagingServicesFeeEvent": "fee",
    "AffordabilityExpenseEvent": "adjustment",
    "AffordabilityExpenseReversalEvent": "adjustment",
}

REIMBURSEMENT_TYPES = {"SAFETReimbursementEvent", "FBALiquidationEvent"}


def _money(charge: dict | None) -> float:
    if not charge:
        return 0.0
    return float(charge.get("CurrencyAmount", 0) or 0)


def _sum_charges(charges: list[dict], component: str) -> float:
    return sum(_money(c.get("ChargeAmount")) for c in charges
               if c.get("ChargeType") == component)


def _sum_fees(fees: list[dict], fee_type: str) -> float:
    return sum(_money(f.get("FeeAmount")) for f in fees
               if f.get("FeeType") == fee_type)


def _parse_dt(s: str | None) -> date_type | None:
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00")).date()
    except Exception:
        return None


def _make_row(txn_date, order_id, settlement_id, txn_type, sku, asin, title,
              qty, gross, promos, referral, fba, other_fees, refunds,
              tax, net, marketplace="Amazon US") -> dict:
    return {
        "date":           txn_date,
        "order_id":       order_id or "",
        "settlement_id":  settlement_id or "",
        "type":           txn_type,
        "sku":            sku or "",
        "asin":           asin or "",
        "title":          title or "",
        "qty":            qty or 0,
        "gross_sales":    round(gross, 2),
        "promotions":     round(promos, 2),
        "referral_fee":   round(referral, 2),
        "fba_fee":        round(fba, 2),
        "other_fees":     round(other_fees, 2),
        "refunds":        round(refunds, 2),
        "sales_tax":      round(tax, 2),
        "net_proceeds":   round(net, 2),
        "marketplace":    marketplace,
        # Derived fields filled later
        "cogs":           0.0,
        "profit_share":   0.0,
        "net_profit":     0.0,
        "margin_pct":     0.0,
        "roi_pct":        0.0,
        "supplier":       "",   # internal; used for profit-share calc
    }


def from_financial_events(events: dict, settlement_id: str = "") -> list[dict]:
    rows = []

    # ---- Shipment events (sales) ----------------------------------------
    for event in events.get("ShipmentEventList", []):
        order_id  = event.get("AmazonOrderId", "")
        posted_dt = _parse_dt(event.get("PostedDate"))
        for item in event.get("ShipmentItemList", []):
            sku   = item.get("SellerSKU", "")
            asin  = item.get("OrderItemId", "")   # SP-API uses OrderItemId, not ASIN here
            title = ""
            qty   = int(item.get("QuantityShipped", 0) or 0)

            charges = item.get("ItemChargeList", [])
            fees    = item.get("ItemFeeList", [])
            promos  = item.get("PromotionList", [])

            gross    = _sum_charges(charges, "Principal")
            tax      = _sum_charges(charges, "Tax")
            shipping = _sum_charges(charges, "ShippingCharge")
            gross   += shipping

            referral = abs(_sum_fees(fees, "ReferralFee"))
            fba_fee  = abs(_sum_fees(fees, "FBAPerUnitFulfillmentFee") +
                           _sum_fees(fees, "FBAPerOrderFulfillmentFee") +
                           _sum_fees(fees, "FBAWeightBasedFee"))
            other    = abs(sum(_money(f.get("FeeAmount")) for f in fees
                               if f.get("FeeType") not in
                               {"ReferralFee", "FBAPerUnitFulfillmentFee",
                                "FBAPerOrderFulfillmentFee", "FBAWeightBasedFee"}))

            promo_amt = abs(sum(_money(p.get("PromotionAmount")) for p in promos))

            net = gross - referral - fba_fee - other - promo_amt

            rows.append(_make_row(posted_dt, order_id, settlement_id, "sale",
                                  sku, asin, title, qty,
                                  gross, -promo_amt, -referral, -fba_fee, -other,
                                  0.0, tax, net))

    # ---- Refund events ---------------------------------------------------
    for event in events.get("RefundEventList", []):
        order_id  = event.get("AmazonOrderId", "")
        posted_dt = _parse_dt(event.get("PostedDate"))
        for item in event.get("ShipmentItemAdjustmentList", []):
            sku  = item.get("SellerSKU", "")
            qty  = int(item.get("QuantityShipped", 0) or 0)

            charges = item.get("ItemChargeAdjustmentList", [])
            fees    = item.get("ItemFeeAdjustmentList", [])

            refund_principal = _sum_charges(charges, "Principal")
            refund_tax       = _sum_charges(charges, "Tax")
            refund_fees      = sum(_money(f.get("FeeAmount")) for f in fees)

            net = refund_principal + refund_fees

            rows.append(_make_row(posted_dt, order_id, settlement_id, "refund",
                                  sku, "", "", qty,
                                  0.0, 0.0, 0.0, 0.0, 0.0,
                                  refund_principal, refund_tax, net))

    # ---- Guarantee / Chargeback events -----------------------------------
    for etype in ("GuaranteeClaimEventList", "ChargebackEventList"):
        for event in events.get(etype, []):
            order_id  = event.get("AmazonOrderId", "")
            posted_dt = _parse_dt(event.get("PostedDate"))
            for item in event.get("ShipmentItemAdjustmentList", []):
                sku = item.get("SellerSKU", "")
                charges = item.get("ItemChargeAdjustmentList", [])
                refund  = _sum_charges(charges, "Principal")
                rows.append(_make_row(posted_dt, order_id, settlement_id, "chargeback",
                                      sku, "", "", 0,
                                      0.0, 0.0, 0.0, 0.0, 0.0,
                                      refund, 0.0, refund))

    # ---- Service fee events ----------------------------------------------
    for event in events.get("ServiceFeeEventList", []):
        posted_dt = _parse_dt(event.get("PostedDate"))
        order_id  = event.get("AmazonOrderId", "")
        fees      = event.get("FeeList", [])
        total_fee = -abs(sum(_money(f.get("FeeAmount")) for f in fees))
        reason    = event.get("FeeReason", "")
        rows.append(_make_row(posted_dt, order_id, settlement_id, "fee",
                              "", "", reason, 0,
                              0.0, 0.0, 0.0, 0.0, total_fee,
                              0.0, 0.0, total_fee))

    # ---- Adjustment events -----------------------------------------------
    for event in events.get("AdjustmentEventList", []):
        posted_dt    = _parse_dt(event.get("PostedDate"))
        adj_type     = event.get("AdjustmentType", "adjustment")
        items        = event.get("AdjustmentItemList", [])
        if items:
            for item in items:
                amt = _money(item.get("TotalAmount"))
                sku = item.get("SellerSKU", "")
                rows.append(_make_row(posted_dt, "", settlement_id, "adjustment",
                                      sku, item.get("ASIN", ""), item.get("Title", ""), 0,
                                      0.0, 0.0, 0.0, 0.0, 0.0,
                                      0.0, 0.0, amt))
        else:
            amt = _money(event.get("AdjustmentAmount"))
            rows.append(_make_row(posted_dt, "", settlement_id, "adjustment",
                                  "", "", adj_type, 0,
                                  0.0, 0.0, 0.0, 0.0, 0.0,
                                  0.0, 0.0, amt))

    # ---- Reimbursement events --------------------------------------------
    for event in events.get("SAFETReimbursementEventList", []):
        posted_dt = _parse_dt(event.get("PostedDate"))
        amt       = _money(event.get("ReimbursedAmount"))
        rows.append(_make_row(posted_dt, "", settlement_id, "reimbursement",
                              "", "", "SAFET Reimbursement", 0,
                              0.0, 0.0, 0.0, 0.0, 0.0,
                              0.0, 0.0, amt))

    for event in events.get("FBALiquidationEventList", []):
        posted_dt   = _parse_dt(event.get("PostedDate"))
        proceeds    = _money(event.get("LiquidationProceedsAmount"))
        fee         = _money(event.get("LiquidationFeeAmount"))
        net         = proceeds - fee
        rows.append(_make_row(posted_dt, "", settlement_id, "reimbursement",
                              "", "", "FBA Liquidation", 0,
                              proceeds, 0.0, 0.0, 0.0, -fee,
                              0.0, 0.0, net))

    # ---- Coupon / promotional events ------------------------------------
    for event in events.get("CouponPaymentEventList", []):
        posted_dt = _parse_dt(event.get("PostedDate"))
        charges   = event.get("ChargeComponent", {})
        fees      = event.get("FeeComponent", {})
        charge_amt = _money(charges)
        fee_amt    = _money(fees)
        net        = charge_amt - abs(fee_amt)
        rows.append(_make_row(posted_dt, "", settlement_id, "adjustment",
                              "", "", "Coupon Payment", 0,
                              0.0, 0.0, 0.0, 0.0, -abs(fee_amt),
                              0.0, 0.0, net))

    # ---- Removal events -------------------------------------------------
    for event in events.get("RemovalShipmentEventList", []):
        posted_dt = _parse_dt(event.get("PostedDate"))
        for item in event.get("RemovalShipmentItemList", []):
            sku = item.get("SellerSKU", "")
            fee = -abs(_money(item.get("RemovalFee")))
            rows.append(_make_row(posted_dt, "", settlement_id, "fee",
                                  sku, "", "Removal Fee", 0,
                                  0.0, 0.0, 0.0, 0.0, fee,
                                  0.0, 0.0, fee))

    # ---- Flag unknown event keys ----------------------------------------
    known_keys = {
        "ShipmentEventList", "RefundEventList", "GuaranteeClaimEventList",
        "ChargebackEventList", "ServiceFeeEventList", "AdjustmentEventList",
        "SAFETReimbursementEventList", "FBALiquidationEventList",
        "CouponPaymentEventList", "RemovalShipmentEventList",
        "ImagingServicesFeeEventList", "AffordabilityExpenseEventList",
        "AffordabilityExpenseReversalEventList", "TDSReimbursementEventList",
        "CapacityReservationBillingEventList", "NetworkComminglingTransactionEventList",
    }
    for key in events:
        if key not in known_keys and events[key]:
            logger.warning("UNKNOWN financial event type '%s' — %d items NOT captured. "
                           "Please report this for mapping.", key, len(events[key]))

    return rows


def dedup(rows: list[dict], seen_ids: set[str]) -> list[dict]:
    """Remove rows whose composite key is already in seen_ids; add new ones."""
    out = []
    for row in rows:
        key = f"{row['order_id']}|{row['settlement_id']}|{row['type']}|{row['sku']}|{row['date']}"
        if key in seen_ids:
            continue
        seen_ids.add(key)
        out.append(row)
    return out
