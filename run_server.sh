#!/bin/bash
# Run from project root — works both locally (with venv) and on Railway/Render (without venv)

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

# Activate venv only if it exists (local dev), skip on cloud platforms
if [ -d "venv" ]; then
  source venv/bin/activate
fi

PYTHONPATH="$SCRIPT_DIR" \
python -m uvicorn backend.api.main:app \
  --host 0.0.0.0 \
  --port "${PORT:-8000}" \
  --timeout-keep-alive 600 \
  --ws-ping-interval 60 \
  --ws-ping-timeout 600