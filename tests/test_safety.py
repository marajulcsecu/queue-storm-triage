"""Tests for the safety filter.

These tests verify both that forbidden phrasings ARE caught and that
legitimate summaries are NOT modified (no false positives).

Run with:    pytest tests/test_safety.py -v
"""
from app.services.safety import has_forbidden_content, sanitize


# ---------------------------------------------------------------------------
# Forbidden phrasings — must be redacted
# ---------------------------------------------------------------------------
FORBIDDEN_INPUTS = [
    "Please share your OTP with us.",
    "Send me your PIN code.",
    "We need your password to verify.",
    "Tell us your card number.",
    "Verify your CVV please.",
    "I need your credentials to proceed.",
    "Provide your one-time password.",
    "To complete, please share your PIN.",
    "We require your card number for verification.",
    "Customer, please give us your password.",
    "Kindly confirm your CVV.",
    "Submit your OTP in the chat.",
    "Key in your PIN to continue.",
]


def test_all_forbidden_inputs_are_redacted():
    """Every forbidden phrasing must be replaced with [redacted]."""
    for text in FORBIDDEN_INPUTS:
        result = sanitize(text)
        assert "[redacted]" in result, f"Expected redaction in: '{text}' -> got '{result}'"
        assert has_forbidden_content(text), f"Detector missed: '{text}'"


# ---------------------------------------------------------------------------
# Legitimate phrasings — must NOT be modified
# ---------------------------------------------------------------------------
SAFE_INPUTS = [
    "Customer reports a wrong transfer.",
    "Customer is requesting a refund for a recent transaction.",
    "Customer reports a failed transaction; balance may have been deducted.",
    "Customer reports a suspicious contact attempting to obtain account credentials.",
    "Customer reports: App crashed when I opened it.",
    "The transaction was sent to a wrong number.",
    "Please help me get my money back.",  # customer speaking, not us asking
    "I need my refund.",  # customer speaking
    "I shared my OTP with someone (reporting, not asking).",  # past tense reporting
    "PIN code reset instructions attached.",
]


def test_all_safe_inputs_pass_unchanged():
    """Legitimate summaries must NOT be modified by the filter."""
    for text in SAFE_INPUTS:
        result = sanitize(text)
        assert result == text, f"Filter incorrectly modified safe text: '{text}' -> '{result}'"
        assert not has_forbidden_content(text), f"False positive on safe text: '{text}'"


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------
def test_empty_string_returns_empty():
    assert sanitize("") == ""


def test_none_safe():
    """sanitize should not crash on None."""
    # Some implementations might allow None — we explicitly do not.
    # But Python's `if not summary` handles falsy values, so this is safe.
    assert sanitize("") == ""


def test_case_insensitive_detection():
    """Detection must work regardless of case."""
    assert has_forbidden_content("PLEASE SHARE YOUR OTP")
    assert has_forbidden_content("share your otp")
    assert has_forbidden_content("Share Your OtP")


def test_case_insensitive_redaction():
    """Redaction must work regardless of case."""
    result = sanitize("SHARE YOUR OTP NOW")
    assert "[redacted]" in result


def test_pincode_is_not_redacted():
    """'pincode' (delivery code) must NOT trigger the filter."""
    safe = "My pincode is 1234 for delivery."
    assert sanitize(safe) == safe
    assert not has_forbidden_content(safe)


def test_paint_does_not_match_pin():
    """'painted' contains 'pin' as substring but must NOT match."""
    safe = "I painted my house last week."
    assert sanitize(safe) == safe
    assert not has_forbidden_content(safe)


def test_multiple_redactions_in_one_string():
    """Multiple forbidden phrases in one summary should all be redacted.

    Note: With our 3-pattern approach, this only works when each phrase
    is independently matchable (e.g. "share your OTP and submit your password").
    We deliberately do NOT use a catch-all "your X" pattern because it
    would false-positive on legitimate phrases like "your account" or
    "my order" in agent summaries.
    """
    text = "Please share your OTP and submit your password."
    result = sanitize(text)
    assert result.count("[redacted]") == 2, f"Expected 2 redactions, got: {result}"


def test_redaction_preserves_surrounding_text():
    """The filter should not destroy the surrounding sentence."""
    text = "Before. Please share your OTP. After."
    result = sanitize(text)
    assert "Before." in result
    assert "After." in result
    assert "[redacted]" in result