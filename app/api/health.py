"""GET /health endpoint.

Moved here from app/main.py in Phase 5 to keep route handlers out of
the application bootstrap file. This is the standard FastAPI pattern:
    - app/main.py creates the app and includes routers
    - app/api/*.py defines the routes

The endpoint itself is unchanged from Phase 2.
"""
from fastapi import APIRouter

from app import __version__

router = APIRouter(tags=["meta"])


@router.get(
    "/health",
    summary="Service liveness probe",
    response_description="Service identity and version.",
)
def health() -> dict:
    """Return 200 OK with service identity.

    Used by Render's health check and by humans verifying deployment.
    """
    return {
        "status": "ok",
        "service": "ticket-triage",
        "version": __version__,
    }