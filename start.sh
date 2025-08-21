#!/usr/bin/env bash
set -euo pipefail
PORT="${PORT:-8000}"
echo "Starting GanadoBravo v36 on 0.0.0.0:${PORT}"
exec uvicorn main:app --host 0.0.0.0 --port "${PORT}" --proxy-headers --forwarded-allow-ips="*" --log-level info --timeout-keep-alive 75
