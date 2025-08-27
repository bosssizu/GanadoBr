#!/usr/bin/env bash
set -e
export PYTHONUNBUFFERED=1
export PORT=${PORT:-8000}
exec uvicorn asgi:app --host 0.0.0.0 --port $PORT --timeout-keep-alive 5
