#!/bin/sh
set -eu

PORT="${PORT:-8000}"

exec python -m uvicorn app.api:app \
    --host 0.0.0.0 \
    --port "${PORT}"
