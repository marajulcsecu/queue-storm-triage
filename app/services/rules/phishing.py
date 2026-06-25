"""Phishing / social engineering detection rule.

This rule has HIGHEST priority per ARCHITECTURE.md ADR-4: if any of the
patterns here match, the ticket is classified as phishing_or_social_engineering
with critical severity, and we skip evaluating any other rule.

Why regex and not keywords? The patterns we care about (mentions of OTP,
PIN, password, CVV, impersonation) are short and predictable. Regex keeps
the rule explicit and easy to extend, and lets us match variations like
"OTP code", "your pin", "send me your password".

Design notes:
    - Case-insensitive (re.IGNORECASE)
    - Word boundaries (\\b) to avoid false matches like "pint" matching "pin"
    - Each pattern is anchored on a specific phishing shape so we get
      high precision. We trade some recall for fewer false positives.

Note on the `pin` lookaround:
    We use a NEGATIVE lookahead that ONLY excludes the single word
    "pincode" (a delivery code, not a banking PIN). It still matches
    "PIN", "pin number", "PIN code", etc.
"""
import re
from typing import Pattern

# Curated list of patterns. Each pattern is intentionally specific to
# reduce false positives while still catching common phish phrasing.
_PATTERNS: list[Pattern[str]] = [
    # ------------------------------------------------------------------
    # Pattern 1: Asking the customer for a credential.
    #   "share your OTP", "send your pin", "give me password",
    #   "verify your card number", "enter your PIN code".
    # ------------------------------------------------------------------
    re.compile(
        r"\b(?:share|send|give|tell|provide|enter|verify|confirm|submit|"
        r"type|key\s+in)\s+"
        r"(?:me\s+|us\s+)?(?:your\s+|the\s+)?"
        r"(?:otp|one[\s-]?time\s+password|pin(?!\s*code\b)|password|passcode|"
        r"cvv|cvc|card\s*(?:number|no)|credentials?)\b",
        re.IGNORECASE,
    ),

    # ------------------------------------------------------------------
    # Pattern 2: Someone ELSE is asking the customer for a credential.
    #   "someone called asking my OTP", "he asked for my PIN",
    #   "they want my password", "the caller is asking for my pin code".
    # The structure: subject + optional words + "ask/asked/asking/want..."
    # + preposition ("for"/"to") + possessive + credential
    # ------------------------------------------------------------------
    re.compile(
        r"\b(?:someone|he|she|they|them|person|caller|scammer|fraudster|"
        r"someone\s+else)\b"
        r"(?:\s+\w+){0,3}\s+"
        r"(?:ask|asked|asking|want|wants|wanted|request|requested|"
        r"requesting|need|needed|needing)\s+"
        r"(?:for\s+|to\s+)?"
        r"(?:me|my|him|her|them|his|hers|theirs|us|our)\s+"
        r"(?:otp|pin|password|cvv|cvc|card(?:\s*(?:number|no))?|credentials?)\b",
        re.IGNORECASE,
    ),

    # ------------------------------------------------------------------
    # Pattern 3: Customer asks if a credential request is legitimate.
    #   "is that really bKash asking for my OTP?",
    #   "is this Nagad support asking for my PIN?"
    # ------------------------------------------------------------------
    re.compile(
        r"\bis\s+(?:it|that|this)\s+(?:really\s+)?"
        r"(?:bkash|nagad|rocket|upay|bank|customer\s+care|support|helpline)\b"
        r"(?:\s+\w+){0,5}\s+"
        r"(?:ask|asked|asking|need|needed|require|required|verify|confirm)\b",
        re.IGNORECASE,
    ),

    # ------------------------------------------------------------------
    # Pattern 4: Past-tense credential disclosure by customer.
    #   "I shared my OTP with the caller",
    #   "I gave my PIN to someone on the phone",
    #   "I told them my password".
    # ------------------------------------------------------------------
    re.compile(
        r"\b(?:i|we)\s+(?:shared|gave|provided|sent|told|entered|submitted|"
        r"typed|keyed)\s+"
        r"(?:my|our|the|them|him|her)\s+"
        r"(?:otp|pin|password|cvv|cvc|card(?:\s*(?:number|no))?)\b",
        re.IGNORECASE,
    ),

    # ------------------------------------------------------------------
    # Pattern 5: Suspicious contact from a "real" provider.
    #   "I got a call from bKash support asking me to verify my PIN",
    #   "received an SMS from Nagad asking for my card number",
    #   "email from the bank asking to confirm my OTP".
    # ------------------------------------------------------------------
    re.compile(
        r"\b(?:got|received|had)\s+(?:a\s+)?"
        r"(?:call|sms|message|email|phone\s+call)\s+"
        r"(?:from\s+)?"
        r"(?:bkash|nagad|rocket|upay|bank|customer\s+care|support|helpline|"
        r"the\s+bank|the\s+wallet)\b"
        r"(?:\s+\w+){0,4}\s+"
        r"(?:ask|asked|asking|want|wants|verify|confirm|share|need)\b",
        re.IGNORECASE,
    ),

    # ------------------------------------------------------------------
    # Pattern 6: Generic "from bKash asking/verifying" — backup if pattern 5
    # is too strict on the leading verb.
    #   "call from bKash asking to verify my PIN",
    #   "SMS from Nagad asking my card number".
    # ------------------------------------------------------------------
    re.compile(
        r"\b(?:call|sms|message|email)\s+from\s+"
        r"(?:bkash|nagad|rocket|upay|bank|customer\s+care|support)\b"
        r"(?:\s+\w+){0,6}\s+"
        r"(?:ask|asked|asking|verify|confirm|share|need|request)\b",
        re.IGNORECASE,
    ),

    # ------------------------------------------------------------------
    # Pattern 7: "sent/received SMS from X asking..." — handles the
    # "They sent an SMS from bKash asking to verify my PIN" case where
    # the contact form is preceded by an action verb.
    # ------------------------------------------------------------------
    re.compile(
        r"\b(?:sms|message|email)\s+from\s+"
        r"(?:bkash|nagad|rocket|upay|bank)\b"
        r"(?:\s+\w+){0,5}\s+"
        r"(?:ask|asked|asking|verify|confirm|share|need|request)\b",
        re.IGNORECASE,
    ),

    # ------------------------------------------------------------------
    # Pattern 8: Final catch-all for "from <provider> asking/verify my <cred>".
    # Anchored on the credential at the end.
    #   "from bKash support asking for my OTP",
    #   "from Nagad asking for my card number",
    #   "from the bank verifying my PIN".
    # ------------------------------------------------------------------
    re.compile(
        r"\bfrom\s+(?:bkash|nagad|rocket|upay|bank|customer\s+care|support)\b"
        r"(?:\s+\w+){0,5}\s+"
        r"(?:ask|asked|asking|verify|verifying|confirm|share|need|request|"
        r"wants?)\b"
        r"(?:\s+\w+){0,3}\s+"
        r"(?:my|your|the|our)\s+"
        r"(?:otp|pin|password|cvv|cvc|card(?:\s*(?:number|no))?|credentials?)\b",
        re.IGNORECASE,
    ),
]


def is_phishing(message: str) -> bool:
    """Return True if the message matches any phishing indicator.

    Args:
        message: Raw customer complaint text.

    Returns:
        True if any pattern matches.
    """
    if not message:
        return False
    return any(pattern.search(message) for pattern in _PATTERNS)


__all__ = ["is_phishing"]


# ----------------------------------------------------------------------
# Quick self-test (only runs when this file is executed directly):
# ----------------------------------------------------------------------
if __name__ == "__main__":
    positives = [
        "Someone called asking my OTP, is that bKash?",
        "He asked for my PIN code",
        "I shared my password with the caller",
        "Please share your OTP with our agent",
        "They sent an SMS from bKash asking to verify my PIN",
        "Is that really Nagad support asking for my card number?",
        "I got a call from bKash support asking me to share my PIN",
        "I gave my OTP to someone on the phone",
    ]
    negatives = [
        "I lost my OTP and cannot login",
        "Please send me my money back",
        "I painted my house last week",
        "My pincode is 1234 for delivery",
        "The support agent was very helpful",
    ]
    print("POSITIVE (should all be True):")
    for m in positives:
        result = is_phishing(m)
        flag = "OK " if result else "FAIL"
        print(f"  [{flag}] ({result}) {m}")
    print("\nNEGATIVE (should all be False):")
    for m in negatives:
        result = is_phishing(m)
        flag = "OK " if not result else "FAIL"
        print(f"  [{flag}] ({result}) {m}")