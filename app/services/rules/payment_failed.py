"""Payment failed detection rule.

Matches messages where the customer reports a transaction failure —
especially when their balance was deducted but the recipient didn't receive
the money. This is a common support case for mobile wallets.

Severity when this matches: HIGH (per ARCHITECTURE.md §7.7).
"""
import re
from typing import Pattern

_PATTERNS: list[Pattern[str]] = [
    # Explicit "payment failed" / "transaction failed" / "payment did not go through".
    re.compile(
        r"\b(?:payment|transaction|transfer|pay|send)\s+"
        r"(?:failed|failure|didn'?t\s+(?:go\s+through|work|happen|complete)|"
        r"was\s+(?:failed|unsuccessful)|not\s+(?:successful|completed|received))\b",
        re.IGNORECASE,
    ),
    # Balance deducted but not received.
    re.compile(
        r"\b(?:balance|money|amount|funds?)\s+(?:was|were|has\s+been|is|got)\s+"
        r"(?:deducted|debited|debited|taken|removed)\b"
        r"(?:\s+\w+){0,8}\s+"
        r"(?:but|however|yet|still\s+not|not\s+received|not\s+credited|haven'?t\s+received)\b",
        re.IGNORECASE,
    ),
    # Shorter: "deducted but not received".
    re.compile(
        r"\b(?:deducted|debited|taken)\s+but\s+(?:not\s+)?(?:received|credited|reflected|arrived)\b",
        re.IGNORECASE,
    ),
    # "Pending" transaction problem.
    re.compile(
        r"\b(?:payment|transaction|transfer)\s+(?:is\s+)?(?:pending|hung|stuck|on\s+hold)\b",
        re.IGNORECASE,
    ),
    # Generic "didn't receive the money" with transfer verb.
    re.compile(
        r"\b(?:didn'?t|haven'?t|hasn'?t|not)\s+receive\s+(?:the\s+)?(?:money|amount|payment|funds?)\b",
        re.IGNORECASE,
    ),
]


def is_payment_failed(message: str) -> bool:
    """Return True if the message describes a failed/debited transaction."""
    if not message:
        return False
    return any(pattern.search(message) for pattern in _PATTERNS)


__all__ = ["is_payment_failed"]