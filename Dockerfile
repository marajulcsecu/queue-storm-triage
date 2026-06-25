# =============================================================================
# QueueStorm CRM Ticket Triage — Production Dockerfile
# =============================================================================
#
# Build:    docker build -t triage-service .
# Run:      docker run -p 8000:8000 triage-service
# Test:     curl http://localhost:8000/health
#
# This is a multi-stage-friendly single-stage image optimized for size.
# Final image uses python:3.12-slim (~150MB) instead of full python (~900MB).
# =============================================================================

FROM python:3.12-slim

# -----------------------------------------------------------------------------
# System dependencies
# -----------------------------------------------------------------------------
# We need only what uvicorn[standard] requires at runtime, which is already
# bundled as Python wheels (uvloop, httptools, websockets). No system libs
# needed beyond what the base image provides.

# -----------------------------------------------------------------------------
# Working directory
# -----------------------------------------------------------------------------
WORKDIR /app

# -----------------------------------------------------------------------------
# Environment defaults
# -----------------------------------------------------------------------------
# PYTHONDONTWRITEBYTECODE: don't create .pyc files (we don't need them in the image)
# PYTHONUNBUFFERED:       force stdout/stderr to be unbuffered (so logs appear immediately)
# PIP_NO_CACHE_DIR:       don't keep pip's download cache (smaller image)
# PIP_DISABLE_PIP_VERSION_CHECK: don't waste time checking for newer pip
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# -----------------------------------------------------------------------------
# Install Python dependencies FIRST (layer caching)
# -----------------------------------------------------------------------------
# Copying requirements.txt alone lets Docker cache the pip install layer.
# Source code changes won't invalidate the dependency layer unless
# requirements.txt itself changes.
COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

# -----------------------------------------------------------------------------
# Copy application source
# -----------------------------------------------------------------------------
COPY app ./app

# -----------------------------------------------------------------------------
# Expose port and define healthcheck
# -----------------------------------------------------------------------------
# 8000 is uvicorn's default. The platform (Render) may override this.
EXPOSE 8000

# Docker-level healthcheck. Render has its own healthcheck but this is
# useful for `docker ps` and standalone Docker deployments.
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health').read()" || exit 1

# -----------------------------------------------------------------------------
# Run the application
# -----------------------------------------------------------------------------
# Use exec form so signals (SIGTERM) reach uvicorn properly. This is
# important for graceful shutdown when Render redeploys.
#
# --host 0.0.0.0  listen on all interfaces (required inside a container)
# --port 8000     match EXPOSE above
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]