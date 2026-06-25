"""POST /sort-ticket endpoint.

Orchestrates the full triage pipeline:
    1. Validate request via Pydantic (TicketRequest)
    2. Classify the message -> (case_type, severity, confidence)
    3. Route to a department based on (case_type, severity)
    4. Build the agent_summary
    5. Sanitize the summary via the safety filter
    6. Compute human_review_required
    7. Return TicketResponse

All request validation errors (missing fields, bad enums, out-of-range)
are handled automatically by FastAPI's Pydantic integration and return
HTTP 422 with field-level details. We do not catch ValidationError here.
"""
import time

from fastapi import APIRouter, status

from app.models.request import TicketRequest
from app.models.response import TicketResponse
from app.models.enums import CaseType, Severity
from app.services.classifier import classify
from app.services.router import route
from app.services.summarizer import build_summary
from app.services.safety import sanitize

# Router for the triage endpoints. Tags group them in /docs.
router = APIRouter(tags=["triage"])


@router.post(
    "/sort-ticket",
    response_model=TicketResponse,
    status_code=status.HTTP_200_OK,
    summary="Classify a customer support ticket",
    responses={
        200: {
            "description": "Ticket classified successfully.",
            "content": {
                "application/json": {
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
            },
        },
        422: {"description": "Validation error in the request payload."},
    },
)
def sort_ticket(payload: TicketRequest) -> TicketResponse:
    """Classify one customer support ticket and return structured output.

    See Mock_Project.docx §2 for the request schema and §3 for the response schema.
    """
    start = time.perf_counter()

    # Step 1: Classify (the heavy lifting; the rest is glue).
    classification = classify(payload.message)

    # Step 2: Determine the owning department.
    department = route(classification.case_type, classification.severity)

    # Step 3: Build the agent summary, then run it through the safety filter.
    # The safety filter is ALWAYS applied — it is a defense-in-depth control,
    # not just a UX nicety (per FR-2.14 in REQUIREMENTS.md).
    raw_summary = build_summary(payload.message, classification.case_type)
    safe_summary = sanitize(raw_summary)

    # Step 4: Compute human_review_required per FR-2.12.
    human_review_required = (
        classification.severity == Severity.CRITICAL
        or classification.case_type == CaseType.PHISHING
    )

    elapsed_ms = (time.perf_counter() - start) * 1000

    # Latency log is intentionally not done here — we'll add structured
    # logging as a middleware in Step 5.4 so ALL endpoints get consistent
    # log lines (including /health and any future routes).
    # We just measure locally so the value is available in the response
    # context if needed.

    return TicketResponse(
        ticket_id=payload.ticket_id,
        case_type=classification.case_type,
        severity=classification.severity,
        department=department,
        agent_summary=safe_summary,
        human_review_required=human_review_required,
        confidence=classification.confidence,
    )