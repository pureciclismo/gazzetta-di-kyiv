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
if ! gsutil -m -h "Cache-Control: public, max-age=0, must-revalidate" \
            cp "$PUBLIC"/*.html "$BUCKET/" 2>>"$PROJECT/logs/gsutil_err.log"; then
    cat "$PROJECT/logs/gsutil_err.log" >> "$REPORT"
    die "gsutil cp of root HTML files failed" 2
fi
if [ -d "$PUBLIC/dossier" ]; then
    if ! gsutil -m -h "Cache-Control: public, max-age=0, must-revalidate" \
                rsync -r -d "$PUBLIC/dossier" "$BUCKET/dossier" 2>>"$PROJECT/logs/gsutil_err.log"; then
        cat "$PROJECT/logs/gsutil_err.log" >> "$REPORT"
        die "gsutil rsync of dossier HTML files failed" 2
    fi
fi
log "DEPLOY: HTML files OK"

# ── Step 3: Deploy data JSONs — private, no-store (live trading data) ──
log "DEPLOY: data/*.json (private, no-store)..."
if ! gsutil -m -h "Cache-Control: private, no-store" \
            cp "$PUBLIC"/data/*.json "$BUCKET/data/" 2>>"$PROJECT/logs/gsutil_err.log"; then
    cat "$PROJECT/logs/gsutil_err.log" >> "$REPORT"
    die "gsutil cp of data JSON files failed" 2
fi
log "DEPLOY: all data JSONs OK"

# ── Step 4: Deploy static assets — cached ──────────────────────────
log "DEPLOY: static assets (css, js, next bundles — 1-day cache)..."
if ! gsutil -m -h "Cache-Control: public, max-age=86400" \
            rsync -r -d -x ".*\.html$|data/.*" "$PUBLIC" "$BUCKET" 2>>"$PROJECT/logs/gsutil_err.log"; then
    cat "$PROJECT/logs/gsutil_err.log" >> "$REPORT"
    log "WARNING: gsutil rsync of static assets encountered some warnings/errors"
fi

# ── Success ────────────────────────────────────────────────────────
echo "[${TIMESTAMP}] deploy OK — index.html + data JSONs + static assets" >> "$REPORT"
log "DONE — all stages complete"
exit 0
