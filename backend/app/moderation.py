"""Content rules. PairUp is for non-sexual, public companionship only."""
import re

_SEXUAL = re.compile(
    r"\b(escort\w*|call\s*-?\s*girl\w*|gigolo\w*|sex\w*|nude\w*|nsfw|hook\s*-?\s*ups?|"
    r"happy\s+ending|full\s+service|body\s*-?\s*(to|2)\s*-?\s*body|b2b|massage\w*|"
    r"one\s*-?\s*night\s*-?\s*stand\w*|fwb|erotic\w*|sensual\w*|adult\s+(service|entertainment)\w*|"
    r"overnight|hotel\s+room|private\s+room|girlfriend\s+experience|gfe|escorting)\b",
    re.I,
)
_PAYMENT = re.compile(
    r"(\b[\w.\-]{2,}@(ok\w+|ybl|ibl|axl|paytm|upi|apl|sbi|hdfcbank|icici)\b|\bgpay\b|\bgoogle\s*pay\b|"
    r"\bphone\s*pe\b|\bphonepe\b|\bpaytm\b|\badvance\s+(payment|booking|fee)\b|\bpay\s+me\b|"
    r"\bwestern\s+union\b|\bcrypto\b|\bgift\s*card\b)",
    re.I,
)
_PHONE = re.compile(r"(?<!\d)(?:\+?91[\s-]?)?[6-9]\d{4}[\s-]?\d{5}(?!\d)")
_EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+")
_LINK = re.compile(r"(https?://|www\.|t\.me/|wa\.me/|instagram\.com|snapchat)", re.I)

RULE = "PairUp is for non-sexual, public companionship only."


def check_text(text: str, context: str = "profile") -> str | None:
    """Return a human-readable reason if text must be rejected, else None.

    context: 'profile' (strictest), 'message', 'booking'
    """
    if not text:
        return None
    if _SEXUAL.search(text):
        return f"This content isn't allowed: sexual or adult-service wording. {RULE}"
    if _PAYMENT.search(text):
        return "Off-platform payment requests (UPI IDs, wallets, advance fees) aren't allowed - they are the most common scam pattern."
    if context == "profile":
        if _PHONE.search(text) or _EMAIL.search(text) or _LINK.search(text):
            return "Don't put phone numbers, emails or links in your public profile. Use in-app chat after a booking is accepted."
    return None
