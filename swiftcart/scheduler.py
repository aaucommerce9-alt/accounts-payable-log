"""
Daily orchestration — called by cron at 5–7 AM.

Flow:
  1. Scan inbox for replies
  2. Discover + pull + filter + score new brands
  3. Screen DNC
  4. Find contact emails
  5. Write personalized emails (Anthropic)
  6. Merge today's follow-ups (due brands)
  7. Split: 20 auto-send (dripped 9 AM–4 PM) + rest to drafts, cap 40/day
  8. Persist everything to Google Sheet
"""
import logging
from datetime import date, timedelta
from typing import Optional

from . import config
from . import alerts
from .contact_finder import find_contact_email
from .dnc import load_dnc, screen
from .email_writer import personalize_email
from .filters import filter_asins, rollup_to_brands, score_and_rank
from .gmail_client import create_draft, drip_send, scan_inbox_for_replies
from .keepa_client import discover_asins, fetch_asin_details
from .models import BrandRecord
from .sheets_client import ensure_header, load_brands, upsert_brand

log = logging.getLogger(__name__)


def run_daily() -> None:
    try:
        _run_daily_inner()
    except Exception as exc:
        log.exception("Daily run crashed")
        alerts.alert_run_failed(exc)
        raise


def _run_daily_inner() -> None:
    log.info("=== SwiftCart daily run started ===")
    today = date.today()

    ensure_header()

    # ── Step 1: Reply detection ───────────────────────────────────────────────
    existing_brands = load_brands()
    sent_brands = [b for b in existing_brands if b.email_status in ("sent", "drafted")]
    scan_inbox_for_replies(sent_brands)
    for b in sent_brands:
        if b.replied:
            upsert_brand(b)

    # ── Step 2–3: Discover new brands ─────────────────────────────────────────
    raw_asins = discover_asins()
    if raw_asins:
        asin_ids = raw_asins  # discover_asins now returns list[str]
        asin_records = fetch_asin_details(asin_ids)
        filtered = filter_asins(asin_records)
        new_brands = rollup_to_brands(filtered)
        new_brands = score_and_rank(new_brands)
    else:
        log.warning("No ASINs from Keepa — skipping discovery")
        new_brands = []

    # ── Step 4: DNC screen ────────────────────────────────────────────────────
    existing_names = {b.name.lower() for b in existing_brands}
    dnc = load_dnc()
    new_brands = screen(new_brands, dnc)
    # Also drop already-tracked brands
    new_brands = [b for b in new_brands if b.name.lower() not in existing_names]

    # ── Step 4b: Set description from category data ───────────────────────────
    for brand in new_brands:
        if brand.categories:
            brand.description = ", ".join(brand.categories[:3])

    # ── Step 5: Find contact emails ───────────────────────────────────────────
    for brand in new_brands:
        email = find_contact_email(brand.name, brand.domain)
        if email:
            brand.contact_email = email
            if "@" in email:
                brand.domain = email.split("@")[1]
        else:
            brand.email_status = "no_contact"
            brand.notes = "no email found"
            upsert_brand(brand)
            log.info("No contact for %s — logged", brand.name)

    contactable_new = [b for b in new_brands if b.contact_email]

    # ── Step 6: Follow-ups due today ─────────────────────────────────────────
    followup_brands = _collect_due_followups(existing_brands, today)
    log.info("Follow-ups due today: %d", len(followup_brands))

    # ── Step 7: Build send queue (priority: follow-ups first, then new) ───────
    queue: list[tuple[BrandRecord, int]] = []   # (brand, followup_num)
    for b in followup_brands:
        if not b.replied:
            queue.append((b, _next_followup_num(b)))
    for b in contactable_new:
        queue.append((b, 0))

    queue = queue[: config.DAILY_SEND_CAP]

    # ── Step 8: Write emails + auto-send all (dripped) ────────────────────────
    brands_to_send = [item[0] for item in queue]
    subjects_bodies = [personalize_email(b, fn) for b, fn in queue]

    def _after_send(brand: BrandRecord, msg_id: str) -> None:
        _mark_sent(brand, today, msg_id)
        upsert_brand(brand)

    drip_send(brands_to_send, subjects_bodies, on_sent=_after_send)

    log.info("=== Daily run done — %d auto-sent ===", len(brands_to_send))


# ── Helpers ───────────────────────────────────────────────────────────────────

def _collect_due_followups(brands: list[BrandRecord], today: date) -> list[BrandRecord]:
    due = []
    for b in brands:
        if b.replied or b.email_status in ("replied", "closed", "dead", "no_contact"):
            continue
        if b.followup1_date == today and not _has_done_followup(b, 1):
            due.append(b)
        elif b.followup2_date == today and not _has_done_followup(b, 2):
            due.append(b)
    return due


def _has_done_followup(brand: BrandRecord, num: int) -> bool:
    marker = f"fu{num}=sent"
    return marker in (brand.notes or "")


def _next_followup_num(brand: BrandRecord) -> int:
    if "fu1=sent" not in (brand.notes or ""):
        return 1
    return 2


def _mark_sent(brand: BrandRecord, today: date, msg_id: str) -> None:
    followup_num = _next_followup_num(brand) if brand.send_date else 0
    brand.email_status = "sent"
    brand.message_id = msg_id
    if not brand.send_date:
        brand.send_date = today
        _set_followup_dates(brand, today)
    if followup_num == 1:
        brand.notes = (brand.notes + " fu1=sent").strip()
    elif followup_num == 2:
        brand.notes = (brand.notes + " fu2=sent").strip()


def _set_followup_dates(brand: BrandRecord, send_date: date) -> None:
    brand.followup1_date = send_date + timedelta(days=config.FOLLOWUP_DAYS[0])
    brand.followup2_date = send_date + timedelta(days=config.FOLLOWUP_DAYS[1])
