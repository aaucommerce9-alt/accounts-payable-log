"""
Email writer — template is 100% locked.
Claude generates ONLY the product-line sentence; everything else is verbatim.
"""
import logging
from anthropic import Anthropic, APIStatusError
from . import config
from . import alerts
from .models import BrandRecord

log = logging.getLogger(__name__)
_client: Anthropic | None = None

# Safe generic fallback used when category data is missing or low-confidence
GENERIC_PRODUCT_LINE = "your product line"


def _get_client() -> Anthropic:
    global _client
    if _client is None:
        _client = Anthropic(api_key=config.ANTHROPIC_API_KEY)
    return _client


def personalize_email(brand: BrandRecord, followup_num: int = 0) -> tuple[str, str]:
    """
    Returns (subject, body).
    The template is rendered verbatim — Claude only fills {product_line}.
    followup_num: 0 = initial, 1 = first follow-up, 2 = second follow-up.
    """
    product_line = _get_product_line_sentence(brand)

    if followup_num == 0:
        body = config.EMAIL_BODY_TEMPLATE.format(
            brand=brand.name,
            product_line=product_line,
        )
        subject = config.EMAIL_SUBJECT
    else:
        body = config.FOLLOWUP_BODY_TEMPLATE.format(
            brand=brand.name,
            product_line=product_line,
        )
        subject = f"Re: {config.EMAIL_SUBJECT}"

    return subject, body


def _get_product_line_sentence(brand: BrandRecord) -> str:
    """
    Ask Claude for ONE short phrase describing the brand's product category.
    Rules enforced in the prompt:
      - Broad category language only (e.g. "pet supplies", "cleaning products")
      - No specific product names, SKUs, model numbers, or brand sub-lines
      - No claims or invented details
      - Falls back to GENERIC_PRODUCT_LINE if category data is absent/thin
    """
    category_hint = _safe_category_hint(brand)

    if not category_hint:
        log.info("No category data for %s — using generic product line", brand.name)
        return GENERIC_PRODUCT_LINE

    prompt = (
        f"Brand name: {brand.name}\n"
        f"Category data from Amazon: {category_hint}\n\n"
        "Write a SHORT phrase (3–6 words) that describes this brand's product category "
        "at a broad level — suitable for this sentence in a wholesale outreach email:\n\n"
        "  'We're interested in carrying {brand}'s [YOUR PHRASE HERE]'\n\n"
        "Rules:\n"
        "- Use broad category language only (e.g. 'pet supplies', 'cleaning products', "
        "'vitamins and supplements', 'home goods')\n"
        "- Do NOT name specific products, SKUs, model numbers, or sub-brands\n"
        "- Do NOT add any claims, adjectives, or invented details\n"
        "- If the category data is too vague to say anything specific, "
        "reply with exactly: your product line\n"
        "- Reply with ONLY the phrase, nothing else"
    )

    try:
        message = _get_client().messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=30,
            messages=[{"role": "user", "content": prompt}],
        )
        phrase = message.content[0].text.strip().strip("'\"").lower()

        # Sanity check: reject if suspiciously long (likely hallucinated detail)
        if len(phrase.split()) > 8 or not phrase:
            log.warning("Claude product-line phrase rejected (too long or empty): %r", phrase)
            return GENERIC_PRODUCT_LINE

        return phrase

    except APIStatusError as exc:
        log.warning("Anthropic API error for %s: %s — using generic product line", brand.name, exc)
        alerts.alert_anthropic_failed(brand.name, exc)
        return GENERIC_PRODUCT_LINE
    except Exception as exc:
        log.warning("Anthropic failed for %s: %s — using generic product line", brand.name, exc)
        alerts.alert_template_fallback(brand.name, str(exc))
        return GENERIC_PRODUCT_LINE


def _safe_category_hint(brand: BrandRecord) -> str:
    """
    Return a category string only if it's genuinely informative.
    Rejects single-word hints and Amazon catch-all categories.
    """
    vague = {"misc", "other", "general", "everything else", "grocery", "health", "beauty",
             "tools", "home", "toys", "sports", "clothing", "shoes", "books", "movies",
             "electronics", "automotive"}

    candidates = [c.strip() for c in (brand.categories or []) if c.strip()]

    # Keep categories that are at least two words or not in the vague set
    good = [c for c in candidates if len(c.split()) >= 2 or c.lower() not in vague]

    if not good:
        return ""

    # Return up to 2 categories joined — enough context, not overwhelming
    return " / ".join(good[:2])
