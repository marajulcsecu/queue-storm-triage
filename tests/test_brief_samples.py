"""Tests for the 5 sample cases in Mock_Project.docx §7.

These tests are the PRIMARY ACCEPTANCE GATE. If any of them fails,
the project does not meet the brief. Each case asserts:
    - HTTP 200
    - ticket_id is echoed correctly
    - case_type matches expected
    - severity matches expected
    - human_review_required is correct (True for phishing/critical, False otherwise)
    - confidence is in [0.0, 1.0]
"""
import pytest


@pytest.mark.parametrize(
    "ticket_id,message,expected_case_type,expected_severity",
    [
        ("T-1", "I sent 3000 to wrong number", "wrong_transfer", "high"),
        ("T-2", "Payment failed but balance deducted", "payment_failed", "high"),
        ("T-3", "Someone called asking my OTP, is that bKash?", "phishing_or_social_engineering", "critical"),
        ("T-4", "Please refund my last transaction, I changed my mind", "refund_request", "low"),
        ("T-5", "App crashed when I opened it", "other", "low"),
    ],
)
def test_brief_sample_case(
    client, ticket_id, message, expected_case_type, expected_severity
):
    """Each brief sample case must produce the expected classification."""
    response = client.post(
        "/sort-ticket",
        json={"ticket_id": ticket_id, "message": message},
    )

    # 1. HTTP status
    assert response.status_code == 200, (
        f"Brief sample {ticket_id} returned {response.status_code}: {response.text}"
    )

    data = response.json()

    # 2. ticket_id echoed
    assert data["ticket_id"] == ticket_id, (
        f"{ticket_id}: expected echo, got '{data['ticket_id']}'"
    )

    # 3. case_type
    assert data["case_type"] == expected_case_type, (
        f"{ticket_id}: expected case_type='{expected_case_type}', "
        f"got '{data['case_type']}'"
    )

    # 4. severity
    assert data["severity"] == expected_severity, (
        f"{ticket_id}: expected severity='{expected_severity}', "
        f"got '{data['severity']}'"
    )

    # 5. department must be one of the 4 valid values
    assert data["department"] in {
        "customer_support", "dispute_resolution", "payments_ops", "fraud_risk"
    }, f"{ticket_id}: invalid department '{data['department']}'"

    # 6. agent_summary must be a non-empty string (and short)
    assert isinstance(data["agent_summary"], str)
    assert 0 < len(data["agent_summary"]) <= 500
    assert data["agent_summary"].strip(), "summary must not be whitespace-only"

    # 7. human_review_required — True iff critical or phishing
    is_critical = data["severity"] == "critical"
    is_phishing = data["case_type"] == "phishing_or_social_engineering"
    expected_review = is_critical or is_phishing
    assert data["human_review_required"] == expected_review, (
        f"{ticket_id}: human_review_required should be {expected_review}, "
        f"got {data['human_review_required']}"
    )

    # 8. confidence in [0.0, 1.0]
    assert 0.0 <= data["confidence"] <= 1.0, (
        f"{ticket_id}: confidence {data['confidence']} out of range"
    )


def test_all_brief_samples_covered(sample_brief_tickets):
    """Sanity: the parametrize list and the fixture should agree."""
    assert len(sample_brief_tickets) == 5


# ---------------------------------------------------------------------------
# Brief sample 3 — specific assertions for the phishing case
# ---------------------------------------------------------------------------
def test_phishing_case_routes_to_fraud_risk(client):
    """Per Mock_Project.docx §4.2: phishing -> fraud_risk."""
    r = client.post("/sort-ticket", json={
        "ticket_id": "T-PHISH",
        "message": "Someone called asking my OTP, is that bKash?",
    })
    assert r.status_code == 200
    data = r.json()
    assert data["department"] == "fraud_risk", (
        f"Phishing must route to fraud_risk, got '{data['department']}'"
    )
    assert data["human_review_required"] is True


def test_wrong_transfer_routes_to_dispute_resolution(client):
    """Per Mock_Project.docx §4.2: wrong_transfer -> dispute_resolution."""
    r = client.post("/sort-ticket", json={
        "ticket_id": "T-WRONG",
        "message": "I sent 5000 to wrong number",
    })
    assert r.status_code == 200
    data = r.json()
    assert data["department"] == "dispute_resolution"


def test_payment_failed_routes_to_payments_ops(client):
    """Per Mock_Project.docx §4.2: payment_failed -> payments_ops."""
    r = client.post("/sort-ticket", json={
        "ticket_id": "T-PAY",
        "message": "Payment failed but balance deducted",
    })
    assert r.status_code == 200
    data = r.json()
    assert data["department"] == "payments_ops"