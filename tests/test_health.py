"""Tests for the /health endpoint.

Per REQUIREMENTS.md:
    - FR-1.1: Return 200 OK
    - FR-1.2: Response within 10 seconds
    - FR-1.3: Body includes at minimum a `status` field with value "ok"
"""


def test_health_returns_200(client):
    """GET /health must return HTTP 200."""
    r = client.get("/health")
    assert r.status_code == 200


def test_health_body_status_ok(client):
    """Body must include status='ok'."""
    r = client.get("/health")
    data = r.json()
    assert data["status"] == "ok"


def test_health_body_includes_service_identity(client):
    """Body should also include service name and version for ops."""
    r = client.get("/health")
    data = r.json()
    assert "service" in data
    assert "version" in data
    assert data["service"] == "ticket-triage"
    assert isinstance(data["version"], str)


def test_health_responds_fast(client):
    """Per FR-1.2: /health must respond within 10 seconds.

    In practice it's milliseconds, but we assert the 10s budget.
    """
    import time
    start = time.perf_counter()
    r = client.get("/health")
    elapsed = time.perf_counter() - start
    assert r.status_code == 200
    assert elapsed < 10.0, f"/health took {elapsed:.2f}s, exceeds 10s budget"