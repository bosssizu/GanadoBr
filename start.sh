#!/usr/bin/env bash
set -e
export PYTHONUNBUFFERED=1
export PORT=${PORT:-8000}
# single worker to simplify for free tiers
exec uvicorn main:app --host 0.0.0.0 --port $PORT
