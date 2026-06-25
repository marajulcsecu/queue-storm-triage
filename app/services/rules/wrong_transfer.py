"""Wrong transfer detection rule.

Matches messages where the customer reports sending money to the wrong
recipient — wrong number, wrong account, mistyped details, etc.

Severity when this matches: HIGH (per ARCHITECTURE.md §7.7).
"""
import re
from typing import Pattern

_PATTERNS: list[Pattern[str]] = [
    # Explicit phrases: "sent to wrong number", "transferred to wrong account",
    # "sent money to wrong person".
    re.compile(
        r"\b(?:sent|transferred|sent\s+money|sent\s+the\s+money|paid)\s+"
        r"(?:to\s+)?(?:the\s+)?wrong\s+"
        r"(?:number|account|person|recipient|number|phone|wallet|id)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:sent|transferred|paid)\s+(?:\d+|\w+)\s+to\s+(?:the\s+)?wrong\b",
        re.IGNORECASE,
    ),
    # "by mistake" + transfer verb.
    re.compile(
        r"\b(?:sent|transferred|paid)\b(?:\s+\w+){0,4}\s+by\s+mistake\b",
        re.IGNORECASE,
    ),
    # "mistyped number/account" — clear wrong-transfer signal.
    re.compile(
        r"\bmistyped?\s+(?:the\s+)?(?:number|account|phone|recipient|wallet)\b",
        re.IGNORECASE,
    ),
    # "wrong number" or "wrong account" near a transfer verb.
    re.compile(
        r"\b(?:wrong\s+number|wrong\s+account|wrong\s+recipient|wrong\s+wallet)\b",
        re.IGNORECASE,
    ),
    # "get it back" / "recover" + transfer verbs — recovery intent.
    re.compile(
        r"\b(?:get|recover|refund|return)\s+(?:it|the\s+money|my\s+money|back)\b",
        re.IGNORECASE,
    ),
]


def is_wrong_transfer(message: str) -> bool:
    """Return True if the message describes a wrong-recipient transfer."""
    if not message:
        return False
    return any(pattern.search(message) for pattern in _PATTERNS)


__all__ = ["is_wrong_transfer"]