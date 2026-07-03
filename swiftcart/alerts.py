"""
Self-alert emails sent to the operator via the existing Gmail OAuth token.
Uses smtplib with OAuth2 XOAUTH2 so no separate password is needed.
Falls back to a plain log entry if the alert itself fails (never crash the run
just because an alert couldn't send).
"""
import base64
import json
import logging
import smtplib
from datetime import datetime
from email.mime.text import MIMEText

from . import config

log = logging.getLogger(__name__)

ALERT_TO = "aaucommerce9@gmail.com"


def _load_token() -> dict:
    with open(config.GMAIL_TOKEN_FILE) as f:
        return json.load(f)


def _refresh_access_token(token_data: dict) -> str:
    """Refresh and return a valid access token using the stored refresh token."""
    import urllib.request, urllib.parse
    params = urllib.parse.urlencode({
        "client_id": token_data["client_id"],
        "client_secret": token_data["client_secret"],
        "refresh_token": token_data["refresh_token"],
        "grant_type": "refresh_token",
    }).encode()
    req = urllib.request.Request(
        "https://oauth2.googleapis.com/token",
        data=params,
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read())["access_token"]


def _xoauth2_string(user: str, access_token: str) -> str:
    return base64.b64encode(
        f"user={user}\x01auth=Bearer {access_token}\x01\x01".encode()
    ).decode()


def _send_alert(subject: str, body: str) -> None:
    try:
        token_data = _load_token()
        access_token = _refresh_access_token(token_data)
        auth_string = _xoauth2_string(config.SENDER_EMAIL, access_token)

        msg = MIMEText(body, "plain")
        msg["To"] = ALERT_TO
        msg["From"] = config.SENDER_EMAIL
        msg["Subject"] = subject

        with smtplib.SMTP("smtp.gmail.com", 587, timeout=15) as smtp:
            smtp.ehlo()
            smtp.starttls()
            smtp.ehlo()
            smtp.docmd("AUTH", "XOAUTH2 " + auth_string)
            smtp.sendmail(config.SENDER_EMAIL, [ALERT_TO], msg.as_string())

        log.info("Alert sent: %s", subject)
    except Exception as exc:
        log.error("Failed to send alert email (%s): %s", subject, exc)


def _ts() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M")


# ── Public alert functions ────────────────────────────────────────────────────

def alert_run_failed(error: Exception) -> None:
    _send_alert(
        subject="[SwiftCart] Daily run FAILED",
        body=(
            f"The SwiftCart daily run crashed at {_ts()}.\n\n"
            f"Error:\n{type(error).__name__}: {error}\n\n"
            "Check swiftcart/logs/run.log for the full traceback.\n"
            "No emails were sent after the point of failure."
        ),
    )


def alert_keepa_exhausted(error: Exception) -> None:
    _send_alert(
        subject="[SwiftCart] Keepa tokens exhausted",
        body=(
            f"Keepa API returned a token-exhaustion error at {_ts()}.\n\n"
            f"Error detail: {error}\n\n"
            "Discovery was skipped for today. Tokens reset on your Keepa billing cycle.\n"
            "Log in at keepa.com to check remaining tokens and reset date."
        ),
    )


def alert_anthropic_failed(brand_name: str, error: Exception) -> None:
    _send_alert(
        subject="[SwiftCart] Anthropic API failed — using template fallback",
        body=(
            f"The Anthropic API failed at {_ts()} while writing an email for: {brand_name}\n\n"
            f"Error detail: {error}\n\n"
            "The hardcoded template was used instead. Check your Anthropic credit balance at\n"
            "console.anthropic.com — if credit is exhausted, top it up to restore personalization.\n\n"
            "Emails sent today may be unPersonalized (template-only)."
        ),
    )


def alert_template_fallback(brand_name: str, reason: str) -> None:
    _send_alert(
        subject="[SwiftCart] Template fallback used",
        body=(
            f"A template fallback occurred at {_ts()} for brand: {brand_name}\n\n"
            f"Reason: {reason}\n\n"
            "The email was sent using the hardcoded template rather than AI personalization."
        ),
    )
