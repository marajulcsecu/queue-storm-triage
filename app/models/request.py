"""Request schema for POST /sort-ticket.

Defines the inbound JSON shape per Mock_Project.docx §2. Pydantic
performs all validation automatically; FastAPI will return HTTP 422
with field-level error details if validation fails.

Field policy:
    - ticket_id: required, non-empty string, echoed back in response
    - channel:   optional enum, one of app/sms/call_center/merchant_portal
    - locale:    optional enum, one of bn/en/mixed
    - message:   required, non-empty string, the actual customer complaint
"""
from typing import Optional

from pydantic import BaseModel, Field

from app.models.enums import Channel, Locale


class TicketRequest(BaseModel):
    """Inbound payload for ticket triage."""
    ticket_id: str = Field(
        ...,
        min_length=1,
        max_length=128,
        description="Opaque ticket identifier echoed back in the response.",
        examples=["T-001"],
    )
    channel: Optional[Channel] = Field(
        default=None,
        description="Originating channel (optional).",
        examples=["app"],
    )
    locale: Optional[Locale] = Field(
        default=None,
        description="Message language hint (optional).",
        examples=["en"],
    )
    message: str = Field(
        ...,
        min_length=1,
        max_length=4000,
        description="Free-text customer complaint (required).",
        examples=["I sent 5000 taka to a wrong number this morning, please help me get it back"],
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "ticket_id": "T-001",
                "channel": "app",
                "locale": "en",
                "message": "I sent 5000 taka to a wrong number this morning, please help me get it back",
            }
        }
    }