"""Per-rule unit tests for the classifier.

These tests verify each individual rule detector in isolation, so a
regression in one rule doesn't get masked by another rule firing first.
The end-to-end classifier tests are in test_brief_samples.py.

Run with:    pytest tests/test_classifier.py -v
"""
import pytest

from app.services.classifier import classify
from app.services.rules import (
    payment_failed,
    phishing,
    refund,
    wrong_transfer,
)
from app.models.enums import CaseType, Severity


# ===========================================================================
# Phishing rule (highest priority)
# ===========================================================================
PHISHING_POSITIVES = [
    "Someone called asking my OTP, is that bKash?",
    "He asked for my PIN code",
    "I shared my password with the caller",
    "Please share your OTP with our agent",
    "They sent an SMS from bKash asking to verify my PIN",
    "Is that really Nagad support asking for my card number?",
    "I got a call from bKash support asking me to share my PIN",
    "I gave my OTP to someone on the phone",
]

PHISHING_NEGATIVES = [
    "I lost my OTP and cannot login",
    "Please send me my money back",
    "I painted my house last week",
    "My pincode is 1234 for delivery",
    "The support agent was very helpful",
    "I sent 5000 to the wrong number",
    "Payment failed but balance deducted",
]


@pytest.mark.parametrize("msg", PHISHING_POSITIVES)
def test_phishing_positives(msg):
    assert phishing.is_phishing(msg) is True, f"Should detect phishing: '{msg}'"


@pytest.mark.parametrize("msg", PHISHING_NEGATIVES)
def test_phishing_negatives(msg):
    assert phishing.is_phishing(msg) is False, f"Should NOT detect phishing: '{msg}'"


# ===========================================================================
# Wrong transfer rule
# ===========================================================================
WRONG_TRANSFER_POSITIVES = [
    "I sent 3000 to wrong number",
    "I transferred money to the wrong account by mistake",
    "Mistyped the number, please help",
    "I want to get my money back",
    "Sent 500 BDT to wrong recipient",
    "I sent the money to a wrong wallet",
    "I paid by mistake to a wrong account",
]


@pytest.mark.parametrize("msg", WRONG_TRANSFER_POSITIVES)
def test_wrong_transfer_positives(msg):
    assert wrong_transfer.is_wrong_transfer(msg) is True


WRONG_TRANSFER_NEGATIVES = [
    "App crashed when I opened it",
    "Please refund my last transaction",
    "Payment failed but balance deducted",
]


@pytest.mark.parametrize("msg", WRONG_TRANSFER_NEGATIVES)
def test_wrong_transfer_negatives(msg):
    assert wrong_transfer.is_wrong_transfer(msg) is False


# ===========================================================================
# Payment failed rule
# ===========================================================================
PAYMENT_FAILED_POSITIVES = [
    "Payment failed but balance deducted",
    "My transaction was unsuccessful",
    "Money deducted but not received",
    "Payment is pending for 2 hours",
    "I did not receive the money",
    "Transaction didn't go through",
]


@pytest.mark.parametrize("msg", PAYMENT_FAILED_POSITIVES)
def test_payment_failed_positives(msg):
    assert payment_failed.is_payment_failed(msg) is True


PAYMENT_FAILED_NEGATIVES = [
    "App crashed when I opened it",
    "I sent to wrong number",
    "Please refund my transaction",
]


@pytest.mark.parametrize("msg", PAYMENT_FAILED_NEGATIVES)
def test_payment_failed_negatives(msg):
    assert payment_failed.is_payment_failed(msg) is False


# ===========================================================================
# Refund rule
# ===========================================================================
REFUND_POSITIVES = [
    "Please refund my last transaction",
    "I want my money back",
    "Please reverse the payment",
    "I changed my mind about this order",
    "Cancel my recent transaction please",
]


@pytest.mark.parametrize("msg", REFUND_POSITIVES)
def test_refund_positives(msg):
    assert refund.is_refund_request(msg) is True


REFUND_NEGATIVES = [
    "App crashed when I opened it",
    "I sent to wrong number",
    "Payment failed but balance deducted",
]


@pytest.mark.parametrize("msg", REFUND_NEGATIVES)
def test_refund_negatives(msg):
    assert refund.is_refund_request(msg) is False


# ===========================================================================
# Classifier orchestrator: priority + confidence + urgency bumps
# ===========================================================================
def test_phishing_priority_overrides_other_rules():
    """A message that matches both phishing and another rule must be phishing."""
    msg = "Someone called asking my OTP, I also sent money to wrong number"
    result = classify(msg)
    assert result.case_type == CaseType.PHISHING
    assert result.severity == Severity.CRITICAL
    assert result.matched_rule == "phishing"


def test_fallback_for_unmatched_messages():
    """Messages that match no rule fall through to 'other' / low severity."""
    result = classify("The weather is nice today")
    assert result.case_type == CaseType.OTHER
    assert result.severity == Severity.LOW
    assert result.matched_rule == "fallback"


def test_urgency_bumps_refund_to_medium():
    """A refund request with urgency cues should bump to medium severity."""
    urgent_msg = "I urgently need my refund processed today"
    result = classify(urgent_msg)
    assert result.case_type == CaseType.REFUND_REQUEST
    assert result.severity == Severity.MEDIUM


def test_changed_my_mind_has_lower_confidence():
    """The 'changed my mind' pattern has lower confidence per the spec."""
    msg = "I changed my mind about the purchase"
    result = classify(msg)
    assert result.case_type == CaseType.REFUND_REQUEST
    assert result.confidence < 0.80, f"Expected conf < 0.80, got {result.confidence}"


def test_confidence_in_range_for_all_case_types():
    """Confidence must be in [0, 1] for every case type."""
    test_messages = [
        "I sent to wrong number",
        "Payment failed",
        "Please refund",
        "Someone asked for my OTP",
        "Random unrelated message",
    ]
    for msg in test_messages:
        r = classify(msg)
        assert 0.0 <= r.confidence <= 1.0, f"Confidence {r.confidence} out of range for: {msg}"


def test_empty_message_falls_through_to_other():
    """An empty string should not crash and should return fallback."""
    result = classify("")
    assert result.case_type == CaseType.OTHER
    assert result.severity == Severity.LOW