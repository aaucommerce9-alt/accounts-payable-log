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
