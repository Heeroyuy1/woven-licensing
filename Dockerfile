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
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY licensing-server/backend/ .

# Environment
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

# Expose API port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Run with uvicorn
CMD uvicorn app.main:app --host 0.0.0.0 --port $PORT --workers 2 --proxy-headers --forwarded-allow-ips "*"
