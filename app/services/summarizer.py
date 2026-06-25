"""Agent summary builder.

Generates a 1-2 sentence neutral description of the ticket for human
agents to scan in two seconds. The summary is always:
    - Neutral (no opinions, no advice)
    - Fact-based (states what the customer reported)
    - Brief (1-2 sentences, under 200 chars preferred)
    - Safe (NEVER asks the customer for credentials — that's the safety
      filter's job, but we also avoid risky phrasings here)

Templates are chosen by case_type. We deliberately do NOT include the
raw message body in the summary because:
    1. It often contains identifying details
    2. It can be longer than the agent has time to read
    3. The structured fields (case_type, severity, department) already
       convey the classification; the summary adds context.
"""
from app.models.enums import CaseType


# Templates per case type. Each is a callable that takes the message
# and returns a string. Keep them deterministic and short.
def _summarize_wrong_transfer(message: str) -> str:
    return "Customer reports sending money to the wrong recipient and is requesting recovery."


def _summarize_payment_failed(message: str) -> str:
    return "Customer reports a failed transaction; balance may have been deducted without the payment completing."


def _summarize_refund(message: str) -> str:
    return "Customer is requesting a refund for a recent transaction."


def _summarize_phishing(message: str) -> str:
    # Be careful here — we explicitly do NOT repeat the phishing message
    # details (e.g. the credential type) because that would echo attacker
    # phrasing back to other agents. Keep it abstract.
    return "Customer reports a suspicious contact attempting to obtain account credentials; immediate review recommended."


def _summarize_other(message: str) -> str:
    # Fallback — use the first sentence of the message if it looks safe.
    first_sentence = message.split(".")[0].strip()
    if 0 < len(first_sentence) <= 150:
        return f"Customer reports: {first_sentence}."
    return "Customer message received but does not match a known issue type."


_SUMMARIZERS = {
    CaseType.WRONG_TRANSFER: _summarize_wrong_transfer,
    CaseType.PAYMENT_FAILED: _summarize_payment_failed,
    CaseType.REFUND_REQUEST: _summarize_refund,
    CaseType.PHISHING: _summarize_phishing,
    CaseType.OTHER: _summarize_other,
}


def build_summary(message: str, case_type: CaseType) -> str:
    """Build the agent_summary string.

    Args:
        message:   The raw customer message.
        case_type: The classified case type.

    Returns:
        A 1-2 sentence neutral summary string.
    """
    summarizer = _SUMMARIZERS.get(case_type, _summarize_other)
    return summarizer(message)


__all__ = ["build_summary"]