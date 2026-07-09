# =============================================================================
# Woven Model Licensing Server — Railway Docker Build
# =============================================================================
# This root-level Dockerfile is required because Railpack cannot handle the
# monorepo root (mixed .bat, .png, etc.). It builds from the licensing-server
# backend subdirectory.
# =============================================================================

FROM python:3.11-slim

WORKDIR /app

# Install runtime deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install
COPY licensing-server/backend/requirements.txt .
COPY licensing-server/scripts/ scripts/
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY licensing-server/backend/ .

# Generate signing keys at build time and bake them into the image
RUN python scripts/genkeys_for_docker.py && echo "Keys generated"

# Environment — set defaults Railway will override via env vars
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1
ENV CORS_ORIGINS=*
ENV DATABASE_URL=sqlite+aiosqlite:///./data/woven_licensing.db

# Create data directory for SQLite
RUN mkdir -p /app/data

# Expose API port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Run with uvicorn
CMD uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --workers 2 --proxy-headers --forwarded-allow-ips "*"
