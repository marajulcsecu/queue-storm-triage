"""Tests for request validation (REQUIREMENTS.md §2.3.1, FR-2.4, FR-2.5).

Verifies that:
    - Malformed JSON returns HTTP 400 (invalid_json)
    - Missing required fields return HTTP 422 (validation_error)
    - Invalid enum values return HTTP 422 (validation_error)
    - Empty required strings return HTTP 422 (validation_error)
    - Wrong field types return HTTP 422 (validation_error)
"""


# ---------------------------------------------------------------------------
# T10: Malformed JSON -> HTTP 400
# ---------------------------------------------------------------------------
def test_malformed_json_returns_400(client):
    """Per FR-2.4: malformed JSON must return HTTP 400."""
    r = client.post(
        "/sort-ticket",
        content=b"this is not valid json {{{",
        headers={"Content-Type": "application/json"},
    )
    assert r.status_code == 400, f"Expected 400, got {r.status_code}: {r.text}"
    data = r.json()
    assert data["error"] == "invalid_json"


def test_empty_body_returns_422(client):
    """Empty body has no JSON to parse, so it fails as missing payload -> 422."""
    r = client.post(
        "/sort-ticket",
        content=b"",
        headers={"Content-Type": "application/json"},
    )
    # Note: an empty body fails Pydantic's "Field required" check, which is 422.
    # Only truly malformed (unparseable) JSON is 400.
    assert r.status_code == 422


def test_truncated_json_returns_400(client):
    """A JSON document that starts but doesn't finish is malformed -> 400."""
    r = client.post(
        "/sort-ticket",
        content=b'{"ticket_id": "T-1"',  # missing closing brace
        headers={"Content-Type": "application/json"},
    )
    assert r.status_code == 400


# ---------------------------------------------------------------------------
# T11: Missing required field -> HTTP 422
# ---------------------------------------------------------------------------
def test_missing_message_returns_422(client):
    """Per FR-2.5: missing required field must return 422."""
    r = client.post("/sort-ticket", json={"ticket_id": "T-1"})
    assert r.status_code == 422
    data = r.json()
    assert data["error"] == "validation_error"
    assert isinstance(data["detail"], list)
    # The detail should mention the missing field
    assert any("message" in str(e.get("loc", [])) for e in data["detail"]), (
        f"Validation error should reference 'message' field: {data['detail']}"
    )


def test_missing_ticket_id_returns_422(client):
    """ticket_id is also required."""
    r = client.post("/sort-ticket", json={"message": "I have a problem"})
    assert r.status_code == 422
    data = r.json()
    assert any("ticket_id" in str(e.get("loc", [])) for e in data["detail"])


def test_empty_object_returns_422(client):
    """An empty JSON object has no required fields -> 422."""
    r = client.post("/sort-ticket", json={})
    assert r.status_code == 422


# ---------------------------------------------------------------------------
# T12: Invalid enum value -> HTTP 422
# ---------------------------------------------------------------------------
def test_invalid_channel_enum_returns_422(client):
    """Per FR-2.3.1: channel must be one of the 4 allowed values."""
    r = client.post("/sort-ticket", json={
        "ticket_id": "T-1",
        "message": "hi",
        "channel": "fax",  # not in the allowed set
    })
    assert r.status_code == 422
    data = r.json()
    assert any("channel" in str(e.get("loc", [])) for e in data["detail"])


def test_invalid_locale_enum_returns_422(client):
    """locale must be one of bn/en/mixed."""
    r = client.post("/sort-ticket", json={
        "ticket_id": "T-1",
        "message": "hi",
        "locale": "fr",  # not allowed
    })
    assert r.status_code == 422


def test_each_valid_enum_accepted(client):
    """All valid enum values must be accepted without error."""
    for channel in ["app", "sms", "call_center", "merchant_portal"]:
        r = client.post("/sort-ticket", json={
            "ticket_id": "T-1",
            "message": "hi",
            "channel": channel,
        })
        assert r.status_code == 200, f"channel '{channel}' should be accepted, got {r.status_code}"

    for locale in ["bn", "en", "mixed"]:
        r = client.post("/sort-ticket", json={
            "ticket_id": "T-1",
            "message": "hi",
            "locale": locale,
        })
        assert r.status_code == 200, f"locale '{locale}' should be accepted, got {r.status_code}"


# ---------------------------------------------------------------------------
# Other validation cases
# ---------------------------------------------------------------------------
def test_empty_message_returns_422(client):
    """Per field constraint: message must have min_length=1."""
    r = client.post("/sort-ticket", json={
        "ticket_id": "T-1",
        "message": "",
    })
    assert r.status_code == 422


def test_empty_ticket_id_returns_422(client):
    """ticket_id must have min_length=1."""
    r = client.post("/sort-ticket", json={
        "ticket_id": "",
        "message": "hi",
    })
    assert r.status_code == 422


def test_ticket_id_must_be_string(client):
    """Wrong type for ticket_id -> 422."""
    r = client.post("/sort-ticket", json={
        "ticket_id": 12345,  # should be string
        "message": "hi",
    })
    assert r.status_code == 422


def test_message_must_be_string(client):
    """Wrong type for message -> 422."""
    r = client.post("/sort-ticket", json={
        "ticket_id": "T-1",
        "message": ["a", "list", "of", "words"],  # should be string
    })
    assert r.status_code == 422


# ---------------------------------------------------------------------------
# Optional fields default to None
# ---------------------------------------------------------------------------
def test_optional_fields_default_to_none(client):
    """channel and locale are optional; response should still be valid."""
    r = client.post("/sort-ticket", json={
        "ticket_id": "T-1",
        "message": "I sent money to wrong number",
        # no channel, no locale
    })
    assert r.status_code == 200
    data = r.json()
    assert data["case_type"] == "wrong_transfer"