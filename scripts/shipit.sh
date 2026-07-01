#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════════════
# shipit.sh — Unified Build + Deploy wrapper for Gazzetta di Kyiv
# ═══════════════════════════════════════════════════════════════════
# Replaces the disjointed gsutil calls with a single robust pipeline
# that injects correct Cache-Control headers at upload time.
#
# Cache strategy:
#   index.html  → public, max-age=0, must-revalidate (always fresh)
#   data/*.json → private, no-store (never cached; live trading data)
#   static assets → public, max-age=86400 (1-day cache; rarely change)
#
# Exit codes: 0=success, 1=build failure, 2=deploy failure
# ═══════════════════════════════════════════════════════════════════

set -euo pipefail

# ── Paths ──────────────────────────────────────────────────────────
PROJECT="${GAZZETTA_HOME:-/opt/gazzetta-di-kyiv}"
VENV_PYTHON="${PROJECT}/venv/bin/python"
PUBLIC="${PROJECT}/public"
SCRIPTS="${PROJECT}/scripts"
BUCKET="gs://www.lagazzettadikyiv.com"
REPORT="${PROJECT}/deploy_report.txt"
TIMESTAMP="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"

log()  { echo "[shipit ${TIMESTAMP}] $*"; }
die()  { log "FATAL: $*"; echo "[${TIMESTAMP}] FATAL: $*" >> "$REPORT"; exit "${2:-1}"; }

# Ensure report dir exists
mkdir -p "$(dirname "$REPORT")" "$PROJECT/logs"

# ── Step 1: Build ──────────────────────────────────────────────────
log "BUILD: running build_frontend.py..."
if ! python3 "$SCRIPTS/build_frontend.py" > "$PROJECT/logs/build_frontend.log" 2>&1; then
    tail -30 "$PROJECT/logs/build_frontend.log" >> "$REPORT"
    die "build_frontend.py failed (see $PROJECT/logs/build_frontend.log)" 1
fi
log "BUILD: OK"

# ── Step 2: Deploy HTML pages — zero-cache, always revalidate ──────
log "DEPLOY: HTML files (max-age=0, must-revalidate)..."
# Find all HTML files recursively in PUBLIC directory
find "$PUBLIC" -name "*.html" -type f | while read -r html_file; do
    # Get the relative path of the HTML file with respect to PUBLIC
    rel_path="${html_file#$PUBLIC/}"
    if ! gsutil -h "Cache-Control: public, max-age=0, must-revalidate" \
                cp "$html_file" "$BUCKET/$rel_path" 2>>"$PROJECT/logs/gsutil_err.log"; then
        cat "$PROJECT/logs/gsutil_err.log" >> "$REPORT"
        die "gsutil cp $rel_path failed" 2
    fi
done
log "DEPLOY: HTML files OK"

# ── Step 3: Deploy data JSONs — private, no-store (live trading data) ──
log "DEPLOY: data/*.json (private, no-store)..."
FAILED_DATA=0
for json_file in "$PUBLIC"/data/*.json; do
    fname="$(basename "$json_file")"
    if ! gsutil -h "Cache-Control: private, no-store" \
                cp "$json_file" "$BUCKET/data/$fname" 2>"$PROJECT/logs/gsutil_err.log"; then
        log "WARNING: Failed to upload $fname — continuing"
        cat "$PROJECT/logs/gsutil_err.log" >> "$REPORT"
        FAILED_DATA=1
    fi
done
if [ "$FAILED_DATA" -eq 1 ]; then
    log "DEPLOY: data JSONs completed with SOME failures (see report)"
else
    log "DEPLOY: all data JSONs OK"
fi

# ── Step 4: Deploy static assets — cached ──────────────────────────
log "DEPLOY: static assets (css, js, next bundles — 1-day cache)..."
find "$PUBLIC" -type f ! -name "*.html" ! -path "$PUBLIC/data/*" | while read -r asset_file; do
    rel_path="${asset_file#$PUBLIC/}"
    if ! gsutil -h "Cache-Control: public, max-age=86400" \
                cp "$asset_file" "$BUCKET/$rel_path" 2>>"$PROJECT/logs/gsutil_err.log"; then
        cat "$PROJECT/logs/gsutil_err.log" >> "$REPORT"
        log "WARNING: Failed to upload static asset $rel_path"
    fi
done

# ── Success ────────────────────────────────────────────────────────
echo "[${TIMESTAMP}] deploy OK — index.html + data JSONs + static assets" >> "$REPORT"
log "DONE — all stages complete"
exit 0
