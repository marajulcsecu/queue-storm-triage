"""QueueStorm CRM Ticket Triage Service.

A stateless HTTP API that reads a single customer support message
and returns a structured classification (case_type, severity,
department, agent_summary, human_review_required, confidence).

Architecture overview (see ARCHITECTURE.md for full details):
    - API layer      -> app/api/        (FastAPI route handlers)
    - Models         -> app/models/     (Pydantic request/response schemas)
    - Services       -> app/services/   (Business logic: classification, summarization, safety)
    - Rules          -> app/services/rules/  (Individual rule detectors)

Entry point: app.main:app
"""
__version__ = "1.0.0"
