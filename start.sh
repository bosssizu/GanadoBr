#!/usr/bin/env bash
set -euo pipefail

# Railway/Heroku-style: honor $PORT (fallback 8000) and bind to 0.0.0.0
PORT="${PORT:-8000}"

# Print environment info
echo "Starting GanadoBravo on 0.0.0.0:${PORT} (uvicorn)"
echo "Python: $(python -V)"
echo "Working dir: $(pwd)"
echo "Listing files:"
ls -la

# Run the app
exec uvicorn main:app   --host 0.0.0.0   --port "${PORT}"   --proxy-headers   --forwarded-allow-ips="*"   --log-level info   --timeout-keep-alive 75
