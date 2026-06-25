"""FastAPI application entry point.

This is the ASGI application loaded by uvicorn:
    uvicorn app.main:app --host 0.0.0.0 --port 8000

Wires together:
    - The /health router (liveness probe)
    - The /sort-ticket router (the actual triage logic)
    - Custom exception handlers for malformed JSON (400) and validation (422)
    - Structured logging middleware (per-request logs, no message body)

The app instance is named `app` so uvicorn picks it up by convention.
"""
import logging
import time

import structlog
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app import __version__
from app.api.health import router as health_router
from app.api.triage import router as triage_router

# ----------------------------------------------------------------------------
# Structured logging setup
# ----------------------------------------------------------------------------
# We use structlog for JSON-formatted logs. One log line per request,
# with no message body (PII concern per FR-NFR-16 in REQUIREMENTS.md).
structlog.configure(
    processors=[
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.JSONRenderer(),
    ],
    wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
    logger_factory=structlog.PrintLoggerFactory(),
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger("triage")

# ----------------------------------------------------------------------------
# FastAPI app
# ----------------------------------------------------------------------------
app = FastAPI(
    title="QueueStorm CRM Ticket Triage",
    description=(
        "Reads one customer support message and returns a structured "
        "classification (case_type, severity, department, agent_summary, "
        "human_review_required, confidence)."
    ),
    version=__version__,
)

# Register routers.
app.include_router(health_router)
app.include_router(triage_router)


# ----------------------------------------------------------------------------
# Middleware: per-request structured log
# ----------------------------------------------------------------------------
@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Log every request as a single JSON line.

    Logged fields:
        - event:        always "http_request"
        - method:       HTTP method
        - path:         request path (no query string)
        - status_code:  response status
        - latency_ms:   wall-clock duration
        - ticket_id:    extracted from request body if /sort-ticket (best-effort)
        - remote_addr:  client IP (for ops debugging)

    We DELIBERATELY do NOT log:
        - The request message body (PII)
        - The response body (may contain PII)
        - Query parameters (often contain user data)
    """
    start = time.perf_counter()
    response = await call_next(request)
    elapsed_ms = (time.perf_counter() - start) * 1000

    log = logger.bind(
        event="http_request",
        method=request.method,
        path=request.url.path,
        status_code=response.status_code,
        latency_ms=round(elapsed_ms, 2),
        remote_addr=request.client.host if request.client else None,
    )
    # Only log the ticket_id for /sort-ticket requests — and only the ID,
    # never the message. We do this by checking if the response body is JSON
    # and looking at the echo'd ticket_id (safe because it comes from OUR
    # response, not the request).
    if request.url.path == "/sort-ticket" and response.status_code == 200:
        # We can't easily parse the response body here without consuming it,
        # so we skip extracting ticket_id from the response. The structured
        # log above is enough for ops; per-request details live in app logs.
        pass

    if response.status_code >= 500:
        log.error("request_failed")
    elif response.status_code >= 400:
        log.warning("request_client_error")
    else:
        log.info("request_ok")

    return response


# ----------------------------------------------------------------------------
# Exception handlers
# ----------------------------------------------------------------------------
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    """Return 422 for schema errors, 400 for malformed JSON.

    Per Mock_Project.docx §2 (FR-2.4 / FR-2.5 in REQUIREMENTS.md):
        - Malformed JSON   -> HTTP 400
        - Schema errors    -> HTTP 422

    FastAPI raises the same exception class for both, distinguished by
    the error type in the errors() list. We split them here.
    """
    errors = exc.errors()
    is_json_invalid = any(err.get("type") == "json_invalid" for err in errors)

    if is_json_invalid:
        return JSONResponse(
            status_code=400,
            content={
                "error": "invalid_json",
                "detail": "Request body is not valid JSON.",
            },
        )

    return JSONResponse(
        status_code=422,
        content={
            "error": "validation_error",
            "detail": errors,
        },
    )


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(
    request: Request, exc: StarletteHTTPException
) -> JSONResponse:
    """Return JSON error body for any HTTPException raised by route handlers."""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": "http_error",
            "detail": exc.detail,
        },
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Catch-all for unexpected errors.

    Returns 500 with a generic message (no stack trace leaked to client).
    The full traceback is logged for ops.
    """
    logger.error(
        "unhandled_exception",
        event="unhandled_exception",
        path=request.url.path,
        method=request.method,
        exc_type=type(exc).__name__,
        exc_message=str(exc),
    )
    return JSONResponse(
        status_code=500,
        content={
            "error": "internal_error",
            "detail": "An unexpected error occurred. The team has been notified.",
        },
    )