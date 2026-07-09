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
# NOTE: Do NOT set DATABASE_URL here. Railway PostgreSQL add-on provides
# postgresql://... via environment. Config.py auto-translates to async driver.
# If no DATABASE_URL is set, the app defaults to SQLite (for local dev).

# Create data directory for SQLite (fallback for local dev)
RUN mkdir -p /app/data

# Copy entrypoint script
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# Expose API port
EXPOSE 8000

# Run via entrypoint for startup diagnostics and dynamic port binding
CMD ["/entrypoint.sh"]
