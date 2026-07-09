#!/bin/bash
set -e

# Print environment info for diagnostics
echo "=== Woven Model Licensing Server Start ==="
echo "PORT=${PORT:-8080}"
echo "DATABASE_URL=$DATABASE_URL"
echo "PYTHONPATH=$PYTHONPATH"
echo "Working directory: $(pwd)"
echo "App main.py exists: $(test -f app/main.py && echo 'yes' || echo 'no')"

# Ensure data directory exists
mkdir -p /app/data

# Start uvicorn with dynamic port
echo "Starting uvicorn on 0.0.0.0:${PORT:-8080}..."
exec uvicorn app.main:app \
    --host 0.0.0.0 \
    --port "${PORT:-8080}" \
    --workers 1 \
    --proxy-headers \
    --forwarded-allow-ips '*'
