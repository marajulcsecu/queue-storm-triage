"""Department routing.

Maps a (case_type, severity) pair to the internal team that should
handle the ticket. Implements the routing table from
ARCHITECTURE.md §7.6.

Routing rules:
    phishing          -> fraud_risk   (always, regardless of severity)
    wrong_transfer    -> dispute_resolution
    payment_failed    -> payments_ops
    refund_request    -> dispute_resolution (MEDIUM+) | customer_support (LOW)
    other             -> customer_support

The refund_request split is the only conditional routing — a simple
"please refund, I changed my mind" goes to customer_support (low
severity, easy to handle), but a contested refund with dispute cues
goes to dispute_resolution.
"""
from app.models.enums import CaseType, Department, Severity

# Default department per case type. Severity overrides are applied below.
_DEFAULT_DEPARTMENT: dict[CaseType, Department] = {
    CaseType.PHISHING: Department.FRAUD_RISK,
    CaseType.WRONG_TRANSFER: Department.DISPUTE_RESOLUTION,
    CaseType.PAYMENT_FAILED: Department.PAYMENTS_OPS,
    CaseType.REFUND_REQUEST: Department.CUSTOMER_SUPPORT,
    CaseType.OTHER: Department.CUSTOMER_SUPPORT,
}


def route(case_type: CaseType, severity: Severity) -> Department:
    """Determine the department that should handle this ticket.

    Args:
        case_type: The classified problem category.
        severity:  The classified urgency.

    Returns:
        The Department enum value.
    """
    # Phishing is ALWAYS fraud_risk, regardless of how it's framed.
    if case_type == CaseType.PHISHING:
        return Department.FRAUD_RISK

    # Refund severity matters: low -> customer_support, medium+ -> dispute_resolution.
    if case_type == CaseType.REFUND_REQUEST and severity in (Severity.MEDIUM, Severity.HIGH, Severity.CRITICAL):
        return Department.DISPUTE_RESOLUTION

    # Default routing for all other cases.
    return _DEFAULT_DEPARTMENT[case_type]


__all__ = ["route"]