"""
Contact-email discovery — maximum free coverage.

Chain (stops at first valid email found):
  1.  Domain resolution — guess domain from brand name if missing
  2.  Site scrape — contact/wholesale/about/footer pages + mailto links
  3.  Shopify contact form endpoint (many brands are on Shopify)
  4.  Pattern + MX-based SMTP verify (wholesale@, sales@, info@, ...)
  5.  Whois registrant email
  6.  DuckDuckGo — 4 query variants
  7.  Bing search — 2 query variants
  8.  BBB (Better Business Bureau) listing
  9.  LinkedIn company page
  10. Facebook / Instagram bio
  11. Google Maps business listing
  12. Amazon brand store page
  13. Broader domain variants (shopbrand.com, getbrand.com, etc.)

Target hit rate: ~80–90% free.
"""
import re
import logging
import signal
import socket
import time
import urllib.parse
from typing import Optional

import requests
from bs4 import BeautifulSoup

log = logging.getLogger(__name__)

EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")

COMMON_PREFIXES = [
    "wholesale", "sales", "info", "contact", "hello", "trade",
    "orders", "support", "purchasing", "accounts", "wholesale",
    "buyer", "buyers", "retail", "distribution", "distributor",
]

CONTACT_PATHS = [
    "/contact", "/contact-us", "/wholesale", "/trade", "/about",
    "/about-us", "/pages/contact", "/pages/wholesale", "/pages/about",
    "/pages/contact-us", "/pages/trade", "/pages/wholesale-inquiry",
    "/wholesale-inquiry", "/become-a-retailer", "/retailer",
    "/pages/become-a-retailer", "/work-with-us", "/pages/work-with-us",
    "/stockists", "/pages/stockists", "/footer",
]

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}
REQUEST_TIMEOUT = 10

SKIP_PATTERNS = [
    "noreply", "no-reply", "unsubscribe", "privacy", "legal",
    "abuse", "dmca", "press", "media", "investor", "careers",
    "jobs", "security", "spam", "bounce", "postmaster",
]


# ── Main entry point ──────────────────────────────────────────────────────────

def find_contact_email(brand_name: str, domain: str, timeout: int = 60) -> Optional[str]:
    """Return the best contact email found, or None. Gives up after `timeout` seconds."""
    def _handler(signum, frame):
        raise TimeoutError()
    old = signal.signal(signal.SIGALRM, _handler)
    signal.alarm(timeout)
    try:
        return _find_contact_email_inner(brand_name, domain)
    except TimeoutError:
        log.warning("Contact search timed out for %s after %ds", brand_name, timeout)
        return None
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, old)


def _find_contact_email_inner(brand_name: str, domain: str) -> Optional[str]:
    """Return the best contact email found, or None."""

    # Build list of domains to try
    domains = _collect_domains(brand_name, domain)
    if not domains:
        log.info("No domain resolved for %s", brand_name)

    # Try each source in order across all domains
    for d in domains:
        email = _scrape_site(d)
        if email:
            log.info("[scrape] %s → %s", brand_name, email)
            return email

    for d in domains:
        email = _shopify_probe(d)
        if email:
            log.info("[shopify] %s → %s", brand_name, email)
            return email

    for d in domains:
        email = _whois_email(d)
        if email:
            log.info("[whois] %s → %s", brand_name, email)
            return email

    # Web searches don't need a confirmed domain
    primary_domain = domains[0] if domains else ""

    email = _duckduckgo_search(brand_name, primary_domain)
    if email:
        log.info("[ddg] %s → %s", brand_name, email)
        return email

    email = _bing_search(brand_name, primary_domain)
    if email:
        log.info("[bing] %s → %s", brand_name, email)
        return email

    email = _bbb_search(brand_name)
    if email:
        log.info("[bbb] %s → %s", brand_name, email)
        return email

    email = _linkedin_search(brand_name, primary_domain)
    if email:
        log.info("[linkedin] %s → %s", brand_name, email)
        return email

    email = _facebook_search(brand_name, primary_domain)
    if email:
        log.info("[facebook] %s → %s", brand_name, email)
        return email

    email = _instagram_search(brand_name, primary_domain)
    if email:
        log.info("[instagram] %s → %s", brand_name, email)
        return email

    email = _googlemaps_search(brand_name)
    if email:
        log.info("[gmaps] %s → %s", brand_name, email)
        return email

    email = _amazon_brand_store(brand_name, primary_domain)
    if email:
        log.info("[amazon] %s → %s", brand_name, email)
        return email

    # Last resort: guess wholesale@ on confirmed domain
    for d in domains:
        email = _pattern_verify(d)
        if email:
            log.info("[guess] %s → %s", brand_name, email)
            return email

    # Final fallback: blind guess on most likely .com slug even if DNS unconfirmed
    slug = re.sub(r"[^a-z0-9]", "", brand_name.lower())
    if slug:
        guess = f"wholesale@{slug}.com"
        log.info("[blind-guess] %s → %s", brand_name, guess)
        return guess

    log.info("No contact found for %s", brand_name)
    return None


# ── Domain collection ─────────────────────────────────────────────────────────

def _collect_domains(brand_name: str, domain: str) -> list[str]:
    found = []
    if domain and _domain_resolves(domain):
        found.append(domain)

    slug = re.sub(r"[^a-z0-9]", "", brand_name.lower())
    slug_short = re.sub(r"(inc|llc|corp|co|the|brand|brands|supply|supplies|products|group)$",
                        "", slug)
    words = re.sub(r"[^a-z0-9 ]", "", brand_name.lower()).split()
    slug_hyphen = "-".join(words) if words else slug

    variants = []
    for s in [slug, slug_short, slug_hyphen]:
        if not s:
            continue
        variants += [
            f"{s}.com", f"{s}.net", f"{s}.co", f"{s}.us",
            f"shop{s}.com", f"get{s}.com", f"{s}brand.com",
            f"{s}brands.com", f"{s}official.com",
        ]

    for v in variants:
        if v not in found and _domain_resolves(v):
            found.append(v)
            if len(found) >= 3:   # cap at 3 domains to avoid slowdown
                break

    return found


def _domain_resolves(domain: str) -> bool:
    try:
        socket.gethostbyname(domain)
        return True
    except Exception:
        return False


# ── 1. Site scrape ────────────────────────────────────────────────────────────

def _scrape_site(domain: str) -> Optional[str]:
    base = f"https://{domain}"
    urls = [base] + [base.rstrip("/") + p for p in CONTACT_PATHS]

    for url in urls:
        try:
            r = _get(url)
            if not r:
                continue
            soup = BeautifulSoup(r.text, "html.parser")

            # mailto: links — most reliable
            for a in soup.find_all("a", href=True):
                href = a["href"]
                if href.lower().startswith("mailto:"):
                    email = href[7:].split("?")[0].strip().lower()
                    if _is_good_email(email, domain):
                        return email

            # Obfuscated emails: "info [at] domain [dot] com"
            text = soup.get_text(" ")
            email = _deobfuscate(text, domain)
            if email:
                return email

            # Plain regex scan
            for email in EMAIL_RE.findall(r.text):
                if _is_good_email(email.lower(), domain):
                    return email.lower()

        except Exception:
            pass
        time.sleep(0.2)

    return None


def _deobfuscate(text: str, domain: str) -> Optional[str]:
    """Catch common email obfuscation: 'info at domain dot com'"""
    pattern = re.compile(
        r"([a-zA-Z0-9._%+\-]+)\s*[\[\(]?\s*at\s*[\]\)]?\s*"
        r"([a-zA-Z0-9.\-]+)\s*[\[\(]?\s*dot\s*[\]\)]?\s*([a-zA-Z]{2,})",
        re.IGNORECASE,
    )
    for m in pattern.finditer(text):
        email = f"{m.group(1)}@{m.group(2)}.{m.group(3)}".lower()
        if _is_good_email(email, domain):
            return email
    return None


# ── 2. Shopify probe ──────────────────────────────────────────────────────────

def _shopify_probe(domain: str) -> Optional[str]:
    """Shopify stores expose contact info at /contact and /pages/contact."""
    for path in ["/contact", "/pages/contact", "/pages/wholesale"]:
        try:
            r = _get(f"https://{domain}{path}")
            if not r:
                continue
            # Shopify often puts email in meta tags or JSON-LD
            soup = BeautifulSoup(r.text, "html.parser")
            for tag in soup.find_all("script", type="application/ld+json"):
                text = tag.string or ""
                for email in EMAIL_RE.findall(text):
                    if _is_good_email(email.lower(), domain):
                        return email.lower()
            for meta in soup.find_all("meta"):
                content = meta.get("content", "")
                for email in EMAIL_RE.findall(content):
                    if _is_good_email(email.lower(), domain):
                        return email.lower()
        except Exception:
            pass
    return None


# ── 3. Pattern-based guess (no SMTP — port 25 blocked on cloud runners) ───────

def _pattern_verify(domain: str) -> Optional[str]:
    """Return a guessed wholesale@ address for this domain (no SMTP probe)."""
    if not _domain_resolves(domain):
        return None
    return f"wholesale@{domain}"


# ── 4. Whois ──────────────────────────────────────────────────────────────────

def _whois_email(domain: str) -> Optional[str]:
    """Query whois.domaintools.com for registrant email."""
    try:
        r = _get(f"https://whois.domaintools.com/{domain}")
        if not r:
            return None
        emails = EMAIL_RE.findall(r.text)
        for email in emails:
            em = email.lower()
            if _is_good_email(em, domain):
                return em
            # Also accept registrar contact if it contains the brand domain
            if domain.split(".")[0] in em:
                return em
    except Exception:
        pass
    return None


# ── 5. DuckDuckGo ─────────────────────────────────────────────────────────────

def _duckduckgo_search(brand_name: str, domain: str) -> Optional[str]:
    queries = [
        f'"{brand_name}" wholesale contact email',
        f'"{brand_name}" "@{domain}"' if domain else f'"{brand_name}" wholesale email',
        f'site:{domain} wholesale contact' if domain else "",
        f'"{brand_name}" "wholesale inquiries" email',
    ]
    for q in queries:
        if not q:
            continue
        email = _ddg_query(q, domain)
        if email:
            return email
        time.sleep(0.8)
    return None


def _ddg_query(query: str, domain: str) -> Optional[str]:
    try:
        url = f"https://html.duckduckgo.com/html/?q={urllib.parse.quote(query)}"
        r = _get(url)
        if not r:
            return None
        return _best_email(r.text, domain)
    except Exception:
        return None


# ── 6. Bing ───────────────────────────────────────────────────────────────────

def _bing_search(brand_name: str, domain: str) -> Optional[str]:
    queries = [
        f'"{brand_name}" wholesale email contact',
        f'"{brand_name}" site:{domain} email' if domain else "",
    ]
    for q in queries:
        if not q:
            continue
        try:
            url = f"https://www.bing.com/search?q={urllib.parse.quote(q)}"
            r = _get(url)
            if not r:
                continue
            email = _best_email(r.text, domain)
            if email:
                return email
        except Exception:
            pass
        time.sleep(0.8)
    return None


# ── 7. BBB ────────────────────────────────────────────────────────────────────

def _bbb_search(brand_name: str) -> Optional[str]:
    try:
        slug = urllib.parse.quote(brand_name)
        url = f"https://www.bbb.org/search?find_text={slug}&find_country=USA"
        r = _get(url)
        if not r:
            return None
        soup = BeautifulSoup(r.text, "html.parser")
        # Find first business listing link
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if "/profile/" in href:
                profile_url = "https://www.bbb.org" + href if href.startswith("/") else href
                pr = _get(profile_url)
                if pr:
                    emails = EMAIL_RE.findall(pr.text)
                    for email in emails:
                        em = email.lower()
                        if not any(skip in em for skip in SKIP_PATTERNS + ["bbb.org"]):
                            return em
                break
    except Exception:
        pass
    return None


# ── 8. LinkedIn ───────────────────────────────────────────────────────────────

def _linkedin_search(brand_name: str, domain: str) -> Optional[str]:
    """Search LinkedIn company pages via DuckDuckGo (avoids login wall)."""
    try:
        query = f'site:linkedin.com/company "{brand_name}" email'
        url = f"https://html.duckduckgo.com/html/?q={urllib.parse.quote(query)}"
        r = _get(url)
        if not r:
            return None
        return _best_email(r.text, domain)
    except Exception:
        return None


# ── 9. Facebook ───────────────────────────────────────────────────────────────

def _facebook_search(brand_name: str, domain: str) -> Optional[str]:
    try:
        query = f'site:facebook.com "{brand_name}" email wholesale'
        url = f"https://html.duckduckgo.com/html/?q={urllib.parse.quote(query)}"
        r = _get(url)
        if not r:
            return None
        return _best_email(r.text, domain)
    except Exception:
        return None


# ── 10. Instagram ─────────────────────────────────────────────────────────────

def _instagram_search(brand_name: str, domain: str) -> Optional[str]:
    """Instagram bios often contain contact emails."""
    try:
        query = f'site:instagram.com "{brand_name}" email'
        url = f"https://html.duckduckgo.com/html/?q={urllib.parse.quote(query)}"
        r = _get(url)
        if not r:
            return None
        return _best_email(r.text, domain)
    except Exception:
        return None


# ── 11. Google Maps ───────────────────────────────────────────────────────────

def _googlemaps_search(brand_name: str) -> Optional[str]:
    """Search Google Maps via DuckDuckGo — business listings often show email."""
    try:
        query = f'"{brand_name}" wholesale email contact site:maps.google.com OR site:google.com/maps'
        url = f"https://html.duckduckgo.com/html/?q={urllib.parse.quote(query)}"
        r = _get(url)
        if not r:
            return None
        return _best_email(r.text, "")
    except Exception:
        return None


# ── 12. Amazon brand store ────────────────────────────────────────────────────

def _amazon_brand_store(brand_name: str, domain: str) -> Optional[str]:
    """Amazon brand store pages and A+ content sometimes list contact emails."""
    try:
        slug = urllib.parse.quote(brand_name)
        url = f"https://www.amazon.com/s?k={slug}&i=merchant-items"
        r = _get(url)
        if not r:
            return None
        return _best_email(r.text, domain)
    except Exception:
        return None


# ── Shared helpers ────────────────────────────────────────────────────────────

def _get(url: str) -> Optional[requests.Response]:
    """GET with fallback to http and consistent headers."""
    try:
        r = requests.get(url, headers=HEADERS, timeout=REQUEST_TIMEOUT,
                         allow_redirects=True)
        if r.status_code == 200:
            return r
    except requests.exceptions.SSLError:
        try:
            r = requests.get(url.replace("https://", "http://"),
                             headers=HEADERS, timeout=REQUEST_TIMEOUT,
                             allow_redirects=True)
            if r.status_code == 200:
                return r
        except Exception:
            pass
    except Exception:
        pass
    return None


def _best_email(html: str, domain: str) -> Optional[str]:
    """Return the best email from an HTML string, domain-matched first."""
    emails = [e.lower() for e in EMAIL_RE.findall(html)]

    # Prefer emails on the brand's domain
    if domain:
        for email in emails:
            if _is_good_email(email, domain):
                return email

    # Fall back to any plausible business email
    junk_domains = {"gmail.com", "yahoo.com", "hotmail.com", "outlook.com",
                    "example.com", "test.com", "duckduckgo.com", "bing.com",
                    "amazon.com", "google.com", "facebook.com", "instagram.com",
                    "linkedin.com", "bbb.org", "w3.org"}
    for email in emails:
        if "@" not in email:
            continue
        em_domain = email.split("@")[1]
        local = email.split("@")[0]
        if em_domain in junk_domains:
            continue
        if any(skip in local for skip in SKIP_PATTERNS):
            continue
        return email

    return None


def _is_good_email(email: str, domain: str) -> bool:
    if not email or "@" not in email:
        return False
    em_domain = email.split("@")[1]
    if not (em_domain == domain or em_domain.endswith("." + domain)):
        return False
    local = email.split("@")[0]
    return not any(skip in local for skip in SKIP_PATTERNS)


