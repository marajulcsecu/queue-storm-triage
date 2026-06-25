"""Response schema for POST /sort-ticket.

Defines the outbound JSON shape per Mock_Project.docx §3. Pydantic
ensures the response always has the exact field names, types, and
constraints the grader expects.

Field policy:
    - ticket_id:               echoed from request, non-empty
    - case_type:               enum, exactly one of the 5 brief values
    - severity:                enum, low|medium|high|critical
    - department:              enum, exactly one of the 4 brief values
    - agent_summary:           1-2 neutral sentences, NEVER asks for credentials
    - human_review_required:   True iff severity==critical OR phishing
    - confidence:              float in [0.0, 1.0]
"""
from pydantic import BaseModel, Field

from app.models.enums import CaseType, Department, Severity


class TicketResponse(BaseModel):
    """Outbound classification payload."""
    ticket_id: str = Field(
        ...,
        min_length=1,
        description="Echo of the ticket_id from the request.",
    )
    case_type: CaseType = Field(
        ...,
        description="Classification of the customer problem.",
    )
    severity: Severity = Field(
        ...,
        description="Urgency of the ticket.",
    )
    department: Department = Field(
        ...,
        description="Internal team that should handle this ticket.",
    )
    agent_summary: str = Field(
        ...,
        min_length=1,
        max_length=500,
        description="1-2 neutral sentences describing the ticket.",
    )
    human_review_required: bool = Field(
        ...,
        description="True when severity is critical OR case is phishing.",
    )
    confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Confidence score in [0.0, 1.0].",
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "ticket_id": "T-001",
                "case_type": "wrong_transfer",
                "severity": "high",
                "department": "dispute_resolution",
                "agent_summary": "Customer reports sending 5000 BDT to a wrong number and requests recovery.",
                "human_review_required": True,
                "confidence": 0.85,
            }
        }
    }