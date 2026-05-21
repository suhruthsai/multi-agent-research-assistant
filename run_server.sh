#!/bin/bash
# Run from project root — increases WebSocket timeout to 10 minutes

cd "/Users/mac/Desktop/multi agent research assisant"
source venv/bin/activate

PYTHONPATH="/Users/mac/Desktop/multi agent research assisant" \
python -m uvicorn backend.api.main:app \
  --reload \
  --port 8000 \
  --timeout-keep-alive 600 \
  --ws-ping-interval 60 \
  --ws-ping-timeout 600