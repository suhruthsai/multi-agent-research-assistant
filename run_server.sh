#!/bin/bash
# Run from project root — works both locally (with venv) and on Render/Railway (without venv)

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

# Activate venv only if it exists (local dev), skip on cloud platforms
if [ -d "venv" ]; then
  source venv/bin/activate
fi

# Render sets $PORT automatically; fall back to 8000 locally
APP_PORT="${PORT:-8000}"

echo "Starting server on host=0.0.0.0 port=$APP_PORT"

PYTHONPATH="$SCRIPT_DIR" \
exec python -m uvicorn backend.api.main:app \
  --host 0.0.0.0 \
  --port "$APP_PORT" \
  --workers 1 \
  --timeout-keep-alive 600 \
  --ws-ping-interval 60 \
  --ws-ping-timeout 600