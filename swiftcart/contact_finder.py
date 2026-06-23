"""
Contact-email discovery chain per spec Section 6:
  1. Scrape brand site (contact/about/wholesale/footer pages)
  2. Pattern-guess common addresses + DNS/SMTP verify
  3. Web search fallback
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
COMMON_PREFIXES = ["info", "sales", "wholesale", "hello", "contact", "hello", "support"]
CONTACT_PATHS = ["/contact", "/contact-us", "/about", "/wholesale", "/trade"]
HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; SwiftCart/1.0; +https://swiftcartsupply.com)"
}
REQUEST_TIMEOUT = 8


def find_contact_email(brand_name: str, domain: str) -> Optional[str]:
    """Return the best email found, or None. Updates domain if blank."""
    if not domain:
        domain = _guess_domain(brand_name)
    if not domain:
        return None

    # Step 1: scrape site pages
    email = _scrape_site(domain)
    if email:
        return email

    # Step 2: pattern + verify
    email = _pattern_verify(domain)
    if email:
        return email

    # Step 3: web search
    email = _web_search(brand_name, domain)
    return email


def _guess_domain(brand_name: str) -> str:
    slug = re.sub(r"[^a-z0-9]", "", brand_name.lower())
    for tld in [".com", ".net", ".co"]:
        domain = slug + tld
        if _domain_resolves(domain):
            return domain
    return ""


def _domain_resolves(domain: str) -> bool:
    try:
        socket.gethostbyname(domain)
        return True
    except Exception:
        return False


def _scrape_site(domain: str) -> Optional[str]:
    base = f"https://{domain}"
    urls_to_try = [base] + [base + path for path in CONTACT_PATHS]
    for url in urls_to_try:
        try:
            r = requests.get(url, headers=HEADERS, timeout=REQUEST_TIMEOUT, allow_redirects=True)
            if r.status_code != 200:
                continue
            emails = EMAIL_RE.findall(r.text)
            for email in emails:
                if _looks_like_contact_email(email, domain):
                    return email.lower()
        except Exception:
            pass
        time.sleep(0.5)
    return None


def _looks_like_contact_email(email: str, domain: str) -> bool:
    em = email.lower()
    dom = domain.lower()
    if not em.endswith(dom):
        return False
    # Exclude common non-human addresses
    skip = ["noreply", "no-reply", "unsubscribe", "privacy", "legal", "abuse"]
    return not any(s in em for s in skip)


def _pattern_verify(domain: str) -> Optional[str]:
    for prefix in COMMON_PREFIXES:
        email = f"{prefix}@{domain}"
        if _smtp_verify(email, domain):
            return email
    return None


def _smtp_verify(email: str, domain: str) -> bool:
    """Basic SMTP RCPT check — not 100% reliable but fast."""
    try:
        import dns.resolver
        mx_records = dns.resolver.resolve(domain, "MX")
        mx = sorted(mx_records, key=lambda r: r.preference)[0].exchange.to_text().rstrip(".")
    except Exception:
        return False

    try:
        with smtplib.SMTP(mx, 25, timeout=5) as smtp:
            smtp.ehlo("swiftcartsupply.com")
            smtp.mail("probe@swiftcartsupply.com")
            code, _ = smtp.rcpt(email)
            return code == 250
    except Exception:
        return False


def _web_search(brand_name: str, domain: str) -> Optional[str]:
    query = urllib.parse.quote(f"{brand_name} wholesale contact email")
    search_url = f"https://html.duckduckgo.com/html/?q={query}"
    try:
        r = requests.get(search_url, headers=HEADERS, timeout=REQUEST_TIMEOUT)
        soup = BeautifulSoup(r.text, "html.parser")
        text = soup.get_text(" ")
        emails = EMAIL_RE.findall(text)
        for email in emails:
            if domain and domain in email.lower():
                return email.lower()
        # Return first plausible business email even without domain match
        for email in emails:
            em = email.lower()
            if not any(bad in em for bad in ["noreply", "example", "test"]):
                return em
    except Exception:
        pass
    return None
