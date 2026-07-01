#!/bin/bash
# continuous_pipeline.sh
# Runs the gazzetta pipeline continuously to provide real-time updates.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT"

echo "=== STARTING CONTINUOUS PIPELINE ==="

while true; do
  echo "=== PIPELINE CHAIN $(date '+%Y-%m-%d %H:%M:%S') ==="
  echo "Delegating to the Sovereign Auditor (governor.py) to manage the pipeline execution..."
  python3 scripts/governor.py
  echo "=== PIPELINE COMPLETE ==="
  
  # Sleep for 5 minutes (300 seconds) before running again
  echo "Waiting 5 minutes for the next cycle..."
  sleep 300
done
