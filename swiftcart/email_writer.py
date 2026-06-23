"""Use Anthropic API to personalize the outreach email per brand."""
import logging
from anthropic import Anthropic, APIStatusError
from . import config
from . import alerts
from .models import BrandRecord

log = logging.getLogger(__name__)
_client: Anthropic | None = None


def _get_client() -> Anthropic:
    global _client
    if _client is None:
        _client = Anthropic(api_key=config.ANTHROPIC_API_KEY)
    return _client


def personalize_email(brand: BrandRecord, followup_num: int = 0) -> tuple[str, str]:
    """
    Returns (subject, body).
    followup_num 0 = initial, 1 = first follow-up, 2 = second follow-up.
    """
    product_line = _describe_product_line(brand)

    if followup_num == 0:
        raw_body = config.EMAIL_BODY_TEMPLATE.format(
            brand=brand.name, product_line=product_line
        )
        system_prompt = (
            "You are an outreach email writer for SwiftCart Supply Inc., a NJ wholesale distributor. "
            "You will receive a draft outreach email and metadata about a brand. "
            "Rewrite the email so it reads naturally for THIS specific brand — keep the structure and claims intact, "
            "but make the product-line reference specific and the tone warm and professional. "
            "Return ONLY the email body, no subject line, no commentary."
        )
    else:
        raw_body = config.FOLLOWUP_BODY_TEMPLATE.format(
            brand=brand.name, product_line=product_line
        )
        system_prompt = (
            "You are writing a brief follow-up to a wholesale outreach email. "
            "Keep it short (3–4 sentences), polite, non-pushy. "
            "Return ONLY the email body, no subject line."
        )

    user_content = (
        f"Brand: {brand.name}\n"
        f"Product line / categories: {product_line}\n"
        f"Est. monthly revenue: ${brand.est_monthly_revenue:,.0f}\n\n"
        f"Draft email:\n{raw_body}"
    )

    try:
        message = _get_client().messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=600,
            system=system_prompt,
            messages=[{"role": "user", "content": user_content}],
        )
        body = message.content[0].text.strip()
    except APIStatusError as exc:
        # Credit exhausted or quota error — alert once and fall back
        log.warning("Anthropic API error for %s: %s — using template", brand.name, exc)
        alerts.alert_anthropic_failed(brand.name, exc)
        body = raw_body
    except Exception as exc:
        log.warning("Anthropic API failed for %s: %s — using template", brand.name, exc)
        alerts.alert_template_fallback(brand.name, str(exc))
        body = raw_body

    subject = config.EMAIL_SUBJECT
    if followup_num > 0:
        subject = f"Re: {subject}"

    return subject, body


def _describe_product_line(brand: BrandRecord) -> str:
    if brand.categories:
        return " / ".join(brand.categories[:2])
    return "products"
