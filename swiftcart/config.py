"""Central configuration — all tunables in one place."""
import os
from dotenv import load_dotenv

load_dotenv()

# ── API keys ──────────────────────────────────────────────────────────────────
KEEPA_API_KEY = os.getenv("KEEPA_API_KEY", "")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
GOOGLE_SHEET_ID = os.getenv("GOOGLE_SHEET_ID", "")

# ── Sender identity ───────────────────────────────────────────────────────────
SENDER_EMAIL = "aaucommerce9@gmail.com"
SENDER_NAME = "SwiftCart Supply Inc."

# ── ASIN-level filters ────────────────────────────────────────────────────────
MIN_SELLERS = 3
MAX_SELLERS = 10
MAX_AMAZON_PRESENT_PCT = 25          # Amazon on listing < 25 % of time
MIN_PRICE_USD = 15.0
MIN_UNITS_PER_MONTH = 50
PRICE_CRASH_LOOKBACK_DAYS = 90
PRICE_CRASH_DROP_PCT = 20            # drop if price fell >20 % in 90 days

# ── Brand-level filters ───────────────────────────────────────────────────────
MIN_BRAND_REVENUE = 50_000
MAX_BRAND_REVENUE = 700_000

# ── Send limits ───────────────────────────────────────────────────────────────
DAILY_SEND_CAP = 40
AUTO_SEND_COUNT = 20
SEND_WINDOW_START_HOUR = 9           # 9 AM
SEND_WINDOW_END_HOUR = 16            # 4 PM

# ── Follow-up cadence ─────────────────────────────────────────────────────────
FOLLOWUP_DAYS = [10, 20]             # day 10 then day 20 from first send
MAX_FOLLOWUPS = 2

# ── Keepa token pacing ────────────────────────────────────────────────────────
KEEPA_TOKEN_PAUSE_SECONDS = 60       # ~1 token/min

# ── Gmail OAuth ───────────────────────────────────────────────────────────────
GMAIL_TOKEN_FILE = os.getenv("GMAIL_TOKEN_FILE", "token.json")
GMAIL_CREDENTIALS_FILE = os.getenv("GMAIL_CREDENTIALS_FILE", "credentials.json")
GMAIL_SCOPES = [
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/gmail.compose",
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.modify",
]

# ── Google Sheets ─────────────────────────────────────────────────────────────
SHEET_HEADERS = [
    "Brand", "Parent", "Domain", "Est. monthly revenue",
    "Avg sellers", "Amazon present %", "Qualifying ASINs",
    "Units/mo", "Score", "Contact email", "Email status",
    "Send date", "Follow-up #1 date", "Follow-up #2 date",
    "Replied?", "Notes",
]

# ── Do-not-contact list ───────────────────────────────────────────────────────
DNC_FILE = os.path.join(os.path.dirname(__file__), "data", "do_not_contact.csv")

# ── Email subject / template ──────────────────────────────────────────────────
EMAIL_SUBJECT = "Wholesale account inquiry — SwiftCart Supply (NJ distributor)"

EMAIL_BODY_TEMPLATE = """\
Hi {brand} Team,

I'm reaching out from SwiftCart Supply Inc. to explore opening a wholesale
account — directly or through your authorized distributor network.

About us: we service 100+ retail accounts, backed by 20+ years of operational
experience. Beyond traditional distribution, we operate as an authorized,
MAP-compliant seller on Amazon and Walmart Marketplace — actively managing
listings, pricing integrity, and channel presence on your behalf — alongside
placement through brick-and-mortar retail and our own DTC platform.

What we bring: strict MAP compliance and brand protection across every channel,
consolidated purchasing power, and full warehousing and logistics out of
Monmouth Junction, NJ.

We're interested in carrying {brand}'s {product_line}, and see strong,
consistent demand within our existing customer base.

Could you share whether you sell direct to qualified retailers or through a
preferred authorized wholesaler for the US Northeast, along with onboarding
requirements, MOQs, and standard terms? Full business documentation is
available on request, and we're ready to move quickly on approval.

Best regards,
SwiftCart Supply Inc.
2 Blue Jay Court, Monmouth Junction, NJ 08852
Phone: 914-625-7091
Email: aaucommerce9@gmail.com\
"""

FOLLOWUP_BODY_TEMPLATE = """\
Hi {brand} Team,

I wanted to follow up on my earlier note about opening a wholesale account
with SwiftCart Supply Inc. We remain very interested in carrying {brand}'s
{product_line} and believe there's strong demand within our network.

Please let me know if you have any questions or if there's a better contact
for wholesale inquiries. Happy to provide full business documentation on request.

Best regards,
SwiftCart Supply Inc.
2 Blue Jay Court, Monmouth Junction, NJ 08852
Phone: 914-625-7091
Email: aaucommerce9@gmail.com\
"""
