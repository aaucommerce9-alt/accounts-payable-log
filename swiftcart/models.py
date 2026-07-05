"""Shared data models."""
from dataclasses import dataclass, field
from datetime import date
from typing import Optional


@dataclass
class AsinRecord:
    asin: str
    brand: str
    title: str
    price_usd: float
    units_per_month: int
    seller_count: int
    amazon_present_pct: float        # 0–100
    price_90d_ago: float
    category: str
    weight_lb: float = 0.0
    fba_fee_usd: float = 0.0          # Keepa pick-and-pack fee, 0 if unavailable


@dataclass
class BrandRecord:
    name: str
    parent: str
    domain: str
    est_monthly_revenue: float
    avg_sellers: float
    amazon_present_pct: float
    qualifying_asins: int
    units_per_month: int
    score: float
    contact_email: str = ""
    email_status: str = "queued"     # queued/drafted/sent/replied/closed/dead
    send_date: Optional[date] = None
    followup1_date: Optional[date] = None
    followup2_date: Optional[date] = None
    replied: bool = False
    notes: str = ""
    # internal use
    categories: list = field(default_factory=list)
    message_id: str = ""             # Gmail Message-ID of sent email
    thread_id: str = ""


@dataclass
class InvoiceLineItem:
    upc: str
    description: str
    cost_per_unit: float
    quantity: int
    supplier_sku: str = ""


@dataclass
class SkuEvaluation:
    upc: str
    asin: str
    description: str
    cost_per_unit: float
    quantity: int
    sell_price: float
    channel: str                     # "FBA" or "FBM"
    referral_fee: float
    fulfillment_fee: float           # FBA pick-and-pack, or FBM shipping+packaging
    total_cost_per_unit: float
    profit_per_unit: float
    margin_pct: float
    roi_pct: float
    units_per_month: int
    seller_count: int
    amazon_present_pct: float
    verdict: str                     # "buy" / "marginal" / "skip"
    reasons: list = field(default_factory=list)
