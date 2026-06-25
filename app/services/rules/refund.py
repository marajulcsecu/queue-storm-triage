"""Refund request detection rule.

Matches messages where the customer explicitly asks for a refund or
reversal of a completed payment. We keep the patterns tight so that
"payment failed" cases (which are routed elsewhere) don't accidentally
trigger here.

Severity when this matches: LOW by default (bumped to MEDIUM in the
classifier if dispute cues are present — see app.services.classifier).
"""
import re
from typing import Pattern

_PATTERNS: list[Pattern[str]] = [
    # Explicit refund / money-back / return requests.
    re.compile(
        r"\b(?:please\s+)?(?:refund|return|reverse|cancel)\s+"
        r"(?:my\s+|the\s+|our\s+)?(?:last\s+|recent\s+)?"
        r"(?:transaction|payment|order|money|amount|purchase|transfer)\b",
        re.IGNORECASE,
    ),
    # "I want my money back" / "give me a refund".
    re.compile(
        r"\b(?:want|need|expect|demand)\s+(?:my\s+|a\s+|the\s+)?"
        r"(?:refund|money\s+back|cashback|chargeback)\b",
        re.IGNORECASE,
    ),
    # "Changed my mind" — common refund trigger phrase.
    re.compile(
        r"\b(?:changed|change)\s+my\s+mind\b",
        re.IGNORECASE,
    ),
    # Generic "I want a refund" with money reference.
    re.compile(
        r"\brefund\s+(?:me|my|the|please)\b",
        re.IGNORECASE,
    ),
]


def is_refund_request(message: str) -> bool:
    """Return True if the message is an explicit refund request."""
    if not message:
        return False
    return any(pattern.search(message) for pattern in _PATTERNS)


__all__ = ["is_refund_request"]