#!/bin/bash
# gazzetta_pipeline_chain.sh — Full data pipeline: intel → decay → flows → build
# Runs every 60m via gazzetta-continuous-capital-flows cron
# Deploy picks up automatically every 15m
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT"

echo "=== PIPELINE CHAIN $(date '+%Y-%m-%d %H:%M:%S') ==="
echo "Delegating to the Sovereign Auditor (governor.py) to manage the pipeline execution..."

# The governor handles all steps, including:
# - Data ingestion (ingestion_triage, market_reality, fetch_cftc, etc.)
# - Synthesis and classification (contradiction_synthesizer, classify_stories)
# - Frontend building (build_frontend)
# - Telegram broadcast (telegram_broadcast)
python3 scripts/governor.py

echo "=== PIPELINE COMPLETE ==="
