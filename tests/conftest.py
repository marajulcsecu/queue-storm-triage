"""Shared pytest fixtures for the test suite.

Provides a TestClient instance that all tests can use to make HTTP
requests to the FastAPI app in-process (no live server needed).

Usage in test files:
    def test_something(client):
        r = client.get('/health')
        assert r.status_code == 200
"""
import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client():
    """FastAPI TestClient bound to the live app instance."""
    return TestClient(app)


@pytest.fixture
def sample_brief_tickets():
    """The 5 brief sample cases from Mock_Project.docx §7.

    Returns a list of (ticket_id, message, expected_case_type, expected_severity)
    tuples that all tests can iterate over.
    """
    return [
        ("T-1", "I sent 3000 to wrong number", "wrong_transfer", "high"),
        ("T-2", "Payment failed but balance deducted", "payment_failed", "high"),
        ("T-3", "Someone called asking my OTP, is that bKash?", "phishing_or_social_engineering", "critical"),
        ("T-4", "Please refund my last transaction, I changed my mind", "refund_request", "low"),
        ("T-5", "App crashed when I opened it", "other", "low"),
    ]