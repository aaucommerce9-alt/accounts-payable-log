"""
Contact-email discovery — reliability-focused chain:
  1. Scrape brand site (contact/about/wholesale/footer pages)
  2. Pattern-guess common prefixes + MX-based SMTP verify
  3. DuckDuckGo web search
  4. Hunter.io (if key set — optional upgrade)

Target hit rate: ~70-80% automatic.
"""
import re
import logging
import socket
import smtplib
import time
import urllib.parse
from typing import Optional

import requests
from bs4 import BeautifulSoup

log = logging.getLogger(__name__)

EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")

# Ordered by likelihood for wholesale outreach
COMMON_PREFIXES = ["wholesale", "sales", "info", "contact", "hello", "trade", "orders", "support"]

CONTACT_PATHS = ["/contact", "/contact-us", "/wholesale", "/trade", "/about", "/about-us",
                 "/pages/contact", "/pages/wholesale", "/pages/about"]

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )
}
REQUEST_TIMEOUT = 10

# Addresses that are never useful for wholesale outreach
SKIP_PATTERNS = ["noreply", "no-reply", "unsubscribe", "privacy", "legal",
                 "abuse", "dmca", "press", "media", "investor", "careers", "jobs"]


def find_contact_email(brand_name: str, domain: str) -> Optional[str]:
    """Return the best contact email found, or None."""
    if not domain:
        domain = _guess_domain(brand_name)
    if not domain:
        log.info("No domain found for %s", brand_name)
        return None

    # Step 1: scrape site pages
    email = _scrape_site(domain)
    if email:
        log.info("Found via scrape: %s → %s", brand_name, email)
        return email

    # Step 2: pattern + SMTP verify
    email = _pattern_verify(domain)
    if email:
        log.info("Found via pattern: %s → %s", brand_name, email)
        return email

    # Step 3: web search
    email = _web_search(brand_name, domain)
    if email:
        log.info("Found via search: %s → %s", brand_name, email)
        return email

    log.info("No contact found for %s (%s)", brand_name, domain)
    return None


# ── Domain guessing ───────────────────────────────────────────────────────────

def _guess_domain(brand_name: str) -> str:
    """Try common TLDs for a slugified brand name."""
    slug = re.sub(r"[^a-z0-9]", "", brand_name.lower())
    # Also try with common words removed
    slug_short = re.sub(r"(inc|llc|corp|co|the|brand|brands)$", "", slug)

    candidates = []
    for s in [slug, slug_short]:
        if s:
            candidates += [s + tld for tld in [".com", ".net", ".co", ".us"]]

    for domain in candidates:
        if _domain_resolves(domain):
            return domain
    return ""


def _domain_resolves(domain: str) -> bool:
    try:
        socket.gethostbyname(domain)
        return True
    except Exception:
        return False


# ── Site scraping ─────────────────────────────────────────────────────────────

def _scrape_site(domain: str) -> Optional[str]:
    base = f"https://{domain}"
    urls = [base] + [base.rstrip("/") + path for path in CONTACT_PATHS]

    seen_urls = set()
    for url in urls:
        if url in seen_urls:
            continue
        seen_urls.add(url)
        try:
            r = requests.get(url, headers=HEADERS, timeout=REQUEST_TIMEOUT,
                             allow_redirects=True)
            if r.status_code != 200:
                continue

            # Check for mailto: links first — most reliable
            soup = BeautifulSoup(r.text, "html.parser")
            for a in soup.find_all("a", href=True):
                href = a["href"]
                if href.startswith("mailto:"):
                    email = href[7:].split("?")[0].strip().lower()
                    if _is_good_email(email, domain):
                        return email

            # Fall back to regex scan of full page text
            emails = EMAIL_RE.findall(r.text)
            for email in emails:
                if _is_good_email(email.lower(), domain):
                    return email.lower()

        except requests.exceptions.SSLError:
            # Try http fallback
            try:
                r = requests.get(url.replace("https://", "http://"),
                                 headers=HEADERS, timeout=REQUEST_TIMEOUT,
                                 allow_redirects=True)
                emails = EMAIL_RE.findall(r.text)
                for email in emails:
                    if _is_good_email(email.lower(), domain):
                        return email.lower()
            except Exception:
                pass
        except Exception:
            pass
        time.sleep(0.3)

    return None


def _is_good_email(email: str, domain: str) -> bool:
    """Email must belong to the brand's domain and not be a system address."""
    if not email or "@" not in email:
        return False
    em_domain = email.split("@")[1]
    # Accept exact domain or subdomain
    if not (em_domain == domain or em_domain.endswith("." + domain)):
        return False
    local = email.split("@")[0]
    return not any(skip in local for skip in SKIP_PATTERNS)


# ── Pattern + SMTP verify ─────────────────────────────────────────────────────

def _pattern_verify(domain: str) -> Optional[str]:
    mx = _get_mx(domain)
    if not mx:
        return None
    for prefix in COMMON_PREFIXES:
        email = f"{prefix}@{domain}"
        if _smtp_verify(email, mx):
            return email
    return None


def _get_mx(domain: str) -> Optional[str]:
    try:
        import dns.resolver
        records = dns.resolver.resolve(domain, "MX")
        return sorted(records, key=lambda r: r.preference)[0].exchange.to_text().rstrip(".")
    except Exception:
        return None


def _smtp_verify(email: str, mx: str) -> bool:
    """SMTP RCPT probe — not 100% reliable but fast and free."""
    try:
        with smtplib.SMTP(mx, 25, timeout=6) as smtp:
            smtp.ehlo("swiftcartsupply.com")
            smtp.mail("probe@swiftcartsupply.com")
            code, _ = smtp.rcpt(email)
            return code == 250
    except Exception:
        return False


# ── Web search ────────────────────────────────────────────────────────────────

def _web_search(brand_name: str, domain: str) -> Optional[str]:
    """Search DuckDuckGo for wholesale/contact email for the brand."""
    for query in [
        f'"{brand_name}" wholesale contact email',
        f'site:{domain} email wholesale contact',
        f'"{brand_name}" "@{domain}"',
    ]:
        email = _ddg_search(query, domain)
        if email:
            return email
        time.sleep(1)
    return None


def _ddg_search(query: str, domain: str) -> Optional[str]:
    encoded = urllib.parse.quote(query)
    url = f"https://html.duckduckgo.com/html/?q={encoded}"
    try:
        r = requests.get(url, headers=HEADERS, timeout=REQUEST_TIMEOUT)
        soup = BeautifulSoup(r.text, "html.parser")
        text = soup.get_text(" ")
        emails = EMAIL_RE.findall(text)
        # Prefer emails on the brand's domain
        for email in emails:
            if domain and _is_good_email(email.lower(), domain):
                return email.lower()
        # Accept any plausible business email as fallback
        for email in emails:
            em = email.lower()
            local = em.split("@")[0] if "@" in em else ""
            if not any(skip in local for skip in SKIP_PATTERNS + ["gmail", "yahoo", "hotmail"]):
                return em
    except Exception:
        pass
    return None
