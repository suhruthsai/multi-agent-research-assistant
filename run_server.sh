#!/bin/bash
# Run from project root — increases WebSocket timeout to 10 minutes

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"
source venv/bin/activate

PYTHONPATH="$SCRIPT_DIR" \
python -m uvicorn backend.api.main:app \
  --reload \
  --port 8000 \
  --timeout-keep-alive 600 \
  --ws-ping-interval 60 \
  --ws-ping-timeout 600