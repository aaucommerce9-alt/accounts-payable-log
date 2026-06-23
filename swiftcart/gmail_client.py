"""Gmail API — send, draft, inbox scan."""
import base64
import logging
import re
import time
from datetime import date, timedelta
from email.mime.text import MIMEText
from typing import Optional

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

from . import config
from .models import BrandRecord

log = logging.getLogger(__name__)


def _get_service():
    creds = None
    try:
        creds = Credentials.from_authorized_user_file(config.GMAIL_TOKEN_FILE, config.GMAIL_SCOPES)
    except Exception:
        pass

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                config.GMAIL_CREDENTIALS_FILE, config.GMAIL_SCOPES
            )
            creds = flow.run_local_server(port=0)
        with open(config.GMAIL_TOKEN_FILE, "w") as token:
            token.write(creds.to_json())

    return build("gmail", "v1", credentials=creds)


def _build_message(to: str, subject: str, body: str) -> dict:
    msg = MIMEText(body, "plain")
    msg["to"] = to
    msg["from"] = f"{config.SENDER_NAME} <{config.SENDER_EMAIL}>"
    msg["subject"] = subject
    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
    return {"raw": raw}


def send_email(brand: BrandRecord, subject: str, body: str) -> str:
    """Send immediately. Returns Gmail message id."""
    svc = _get_service()
    msg = _build_message(brand.contact_email, subject, body)
    result = svc.users().messages().send(userId="me", body=msg).execute()
    log.info("Sent to %s (%s) — id=%s", brand.name, brand.contact_email, result["id"])
    return result["id"]


def create_draft(brand: BrandRecord, subject: str, body: str) -> str:
    """Create a Gmail draft. Returns draft id."""
    svc = _get_service()
    msg = _build_message(brand.contact_email, subject, body)
    result = svc.users().drafts().create(userId="me", body={"message": msg}).execute()
    log.info("Draft created for %s — id=%s", brand.name, result["id"])
    return result["id"]


def drip_send(
    brands_to_auto_send: list[BrandRecord],
    subjects_bodies: list[tuple[str, str]],
) -> list[str]:
    """
    Send emails dripped across SEND_WINDOW_START_HOUR–SEND_WINDOW_END_HOUR.
    Returns list of message IDs.
    """
    count = len(brands_to_auto_send)
    if count == 0:
        return []

    window_seconds = (config.SEND_WINDOW_END_HOUR - config.SEND_WINDOW_START_HOUR) * 3600
    interval = window_seconds / count

    message_ids = []
    for brand, (subject, body) in zip(brands_to_auto_send, subjects_bodies):
        msg_id = send_email(brand, subject, body)
        message_ids.append(msg_id)
        if interval > 1:
            time.sleep(interval)

    return message_ids


def scan_inbox_for_replies(brands: list[BrandRecord]) -> list[str]:
    """
    Scan the Gmail inbox for replies to previously sent emails.
    Returns list of brand names that replied.
    """
    svc = _get_service()
    replied_brands: list[str] = []

    # Build lookup maps
    domain_to_brand: dict[str, BrandRecord] = {}
    thread_to_brand: dict[str, BrandRecord] = {}
    msgid_to_brand: dict[str, BrandRecord] = {}

    for b in brands:
        if b.domain:
            domain_to_brand[b.domain.lower()] = b
        if b.thread_id:
            thread_to_brand[b.thread_id] = b
        if b.message_id:
            msgid_to_brand[b.message_id] = b

    try:
        results = svc.users().messages().list(
            userId="me", labelIds=["INBOX"], maxResults=100
        ).execute()
        messages = results.get("messages", [])
    except Exception as exc:
        log.error("Gmail inbox scan failed: %s", exc)
        return []

    for m in messages:
        try:
            msg = svc.users().messages().get(
                userId="me", id=m["id"], format="metadata",
                metadataHeaders=["From", "Subject", "In-Reply-To", "References"],
            ).execute()
        except Exception:
            continue

        headers = {h["name"]: h["value"] for h in msg.get("payload", {}).get("headers", [])}
        from_addr = headers.get("From", "").lower()
        in_reply_to = headers.get("In-Reply-To", "")
        references = headers.get("References", "")
        thread_id = msg.get("threadId", "")

        matched_brand: Optional[BrandRecord] = None

        # 1. Thread match
        if thread_id in thread_to_brand:
            matched_brand = thread_to_brand[thread_id]

        # 2. In-Reply-To / References header match
        if not matched_brand:
            for ref in re.split(r"\s+", f"{in_reply_to} {references}"):
                ref = ref.strip("<>")
                if ref in msgid_to_brand:
                    matched_brand = msgid_to_brand[ref]
                    break

        # 3. Domain match
        if not matched_brand:
            m_domain = _extract_domain(from_addr)
            if m_domain and m_domain in domain_to_brand:
                matched_brand = domain_to_brand[m_domain]

        if matched_brand:
            log.info("Reply matched → %s", matched_brand.name)
            matched_brand.replied = True
            matched_brand.email_status = "replied"
            replied_brands.append(matched_brand.name)
        else:
            _log_ambiguous_reply(headers)

    return replied_brands


def _extract_domain(email_str: str) -> str:
    m = re.search(r"@([\w.\-]+)", email_str)
    return m.group(1).lower() if m else ""


def _log_ambiguous_reply(headers: dict) -> None:
    log.warning(
        "Ambiguous reply — flagged for operator review. From: %s Subject: %s",
        headers.get("From", "?"),
        headers.get("Subject", "?"),
    )
