"""Do-not-contact list loader and matcher."""
import csv
import logging
import os
from .models import BrandRecord
from . import config

log = logging.getLogger(__name__)


def load_dnc() -> list[dict]:
    """
    CSV columns: brand, parent, domain  (header row required)
    Returns list of dicts; empty list if file missing.
    """
    if not os.path.exists(config.DNC_FILE):
        log.warning("DNC file not found at %s — running with empty block list", config.DNC_FILE)
        return []

    entries = []
    with open(config.DNC_FILE, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            entries.append({
                "brand": (row.get("brand") or "").strip().lower(),
                "parent": (row.get("parent") or "").strip().lower(),
                "domain": (row.get("domain") or "").strip().lower(),
            })
    log.info("DNC list loaded: %d entries", len(entries))
    return entries


def screen(brands: list[BrandRecord], dnc: list[dict]) -> list[BrandRecord]:
    if not dnc:
        return brands

    blocked_brands, blocked_parents, blocked_domains = set(), set(), set()
    for entry in dnc:
        if entry["brand"]:
            blocked_brands.add(entry["brand"])
        if entry["parent"]:
            blocked_parents.add(entry["parent"])
        if entry["domain"]:
            blocked_domains.add(entry["domain"])

    kept = []
    for b in brands:
        brand_key = b.name.lower()
        parent_key = b.parent.lower()
        domain_key = b.domain.lower()

        if brand_key in blocked_brands or parent_key in blocked_parents or domain_key in blocked_domains:
            log.info("DNC block: %s", b.name)
        else:
            kept.append(b)

    log.info("DNC screen: %d → %d brands", len(brands), len(kept))
    return kept
