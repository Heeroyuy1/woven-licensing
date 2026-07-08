# =============================================================================
# Woven Model Licensing Server — Production Docker Image
# =============================================================================
# Multi-stage build: install deps in stage 1, run in minimal stage 2.
#
# Build:   docker build -t woven-model/licensing-server:latest .
# Run:     docker run -p 8000:8000 woven-model/licensing-server:latest
#
# Requires: .env.production, signing keys, and a data volume for SQLite.
# =============================================================================

# ── Stage 1: Dependencies ────────────────────────────────────────────────────
FROM python:3.11-slim AS builder

WORKDIR /build

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libc6-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt


# ── Stage 2: Runtime ─────────────────────────────────────────────────────────
FROM python:3.11-slim AS runtime

# Create non-root user
RUN groupadd -r woven && useradd -r -g woven -d /app -s /sbin/nologin woven

# Install runtime system deps only (curl for healthcheck)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Copy installed packages from builder
COPY --from=builder /root/.local /root/.local
ENV PATH=/root/.local/bin:$PATH

# Application directory
WORKDIR /app

# Copy application code
COPY backend/ .

# Create data directory for SQLite database
RUN mkdir -p /app/data && chown -R woven:woven /app/data

# Generate signing keys if not present (runs at build time)
RUN python scripts/generate_keys.py || true

# Environment
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

# Expose API port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Switch to non-root user
USER woven

# Run with uvicorn
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2", "--proxy-headers", "--forwarded-allow-ips", "*"]
