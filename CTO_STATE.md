# CTO State Persistence Protocol — La Gazzetta di Kyiv
# Updated: 2026-06-27 ~17:15 Kyiv (PHASE 11 — CFTC FINANCIAL FUTURES COMPLETE ✅)

## Phase 11: CFTC Financial Futures Integration — COMPLETED ✅
- New: fetch_cftc_financial.py — downloads TIFF ZIP (fut_fin_xls_2026.zip), extracts CSV,
  filters 8 financial contracts, outputs cftc_financial_positions.json
- 48-hour cache: protects VM bandwidth, prevents CFTC IP blocks (data is weekly)
- Updated calculate_capital.py: dual-source CFTC ingestion (physical + financial),
  correct notional multipliers (6E=$135K, ZN=$100K, ES=$280K, NQ=$430K),
  $10T narrative-level circuit breaker
- Governor step: cftc_financial after cftc_data (90s timeout, non-critical)
- Live capital: rate_cycle $165B, tech_convergence $70.5B, dollar_decline $0.7B
- All 13 narratives now have live capital values — ZERO N/A gaps
- TIFF contract codes (verified live, 2026-06-27):
  099741/Euro FX, 097741/Japanese Yen, 096742/British Pound,
  042601/2Y Note, 043602/10Y Note, 020601/30Y Bond,
  13874A/S&P E-mini, 209742/Nasdaq Mini
- NOTE: CFTC blocks VM IP for TIFF download — ship cached ZIP+XLS to VM
  (or set up proxy/VPN for VM outbound)
# Read this at the START of every session.
# NOTE: The assistant should utilize native MCP tools (e.g. datacloud, chrome-devtools)
# and command tools directly to inspect schemas, execute DB queries, or run diagnostics.
# Do not generate one-off python shell wrapper scripts for tasks covered by MCP.


## Bilingual Architecture — COMPLETED ✅
- translate_ru.py: GLM 5.2 batch translation with ID-tracked ledger
- build_frontend.py --lang ru: Russian HTML output to ru/index.html
- governor.py: translate_ru + build_ru steps (non-blocking)
- test_platform.py: 4 RU assertions, 161/161 PERFECT BOARD
- Russian trading-desk nomenclature: лонг, шорт, стоп-лосс, тейк-профит, дивергенция, альфа-триггер
- 5 stories translated and quality-verified live

## Architecture State

### Infrastructure
- **VM**: gazzetta-prod (e2-micro, us-central1-a, 3.8GB RAM, 30GB disk, 4.2GB used)
- **Project root**: /opt/gazzetta-di-kyiv/
- **User**: gazzetta (all pipeline processes)
- **Python venv**: /opt/gazzetta-di-kyiv/venv/bin/python
- **Deploy**: shipit.sh → gsutil cp (html: no-cache, json: no-store, static: 1d) → GCS → CDN
- **Scheduler**: systemd timer gazzetta-governor.timer (10-min cycle)
- **SSH alias**: gazzetta-prod
- **Local repo**: ~/lagazzettadikyiv/
- **Git remote**: https://github.com/pureciclismo/gazzetta-di-kyiv (HTTPS, pureciclismo token)
- **gsutil**: /opt/gazzetta-di-kyiv/devvit/google-cloud-sdk/bin/gsutil
- **DB**: /opt/gazzetta-di-kyiv/data/gazzetta.db (must use `sudo -u gazzetta sqlite3`)

### Pipeline (17 steps)
youtube → arxiv → ingestion → market_data → cftc_data → cftc_financial → fred_data → derivatives
→ synthesis → classify → calc_capital → gen_flows → build_frontend → test_platform
→ telegram_post → deploy

### Active Scripts (26)
build_frontend.py (1720L), contradiction_synthesizer.py (1069L), governor.py,
calculate_capital.py, classify_stories.py, db_to_json.py,
fetch_arxiv.py, fetch_cftc.py, fetch_derivatives.py, fetch_fred.py,
fetch_narrative_cap.py, fetch_patents.py, fetch_youtube.py, generate_flows.py,
health_check.py, ingestion_triage.py, market_reality.py, narrative_pulse.py,
purge_cache.py, shipit.sh, telegram_broadcast.py, telegram_stats.py, test_platform.py,
traffic_cop.py, build_dossiers.py

> deploy_to_gcs.py retained as fallback but NO LONGER USED — governor delegates to shipit.sh

### Key Data Files
- stories.json: public/data/stories.json (600 stories, 6.8MB)
- flows.json: public/data/flows.json (12 narratives)
- narratives.json: data/narratives.json (12 narratives with tickers)
- narrative_graph.json: data/narrative_graph.json (67 assets)
- narrative_cap.json: data/narrative_cap.json ($18.28T total NMC)
- derivatives.json: public/data/derivatives.json
- gazzetta.db: SQLite database

## Phase C — Completed Today (Jun 26–27)

### C1: GAP → Δ Edge (Contrarian Edge) Semantic Transition
- 31 patches to build_frontend.py: all user-facing "GAP" replaced with "Δ Edge"
- 16 patches to telegram_broadcast.py: gap_to_tag→edge_tag, hashtags, format strings
- Crosshair axis: "Δ Edge (Contrarian Edge) →"
- Leaderboard: "Δ EDGE LEADERBOARD" with "Δ 94", "Δ 81" etc.
- Story cards: "Δ EDGE 63" instead of "GAP 63"
- Capital Flows, About, Contradictions tabs: all Δ Edge
- Meta tags updated (Contrarian Edge (Δ) between media consensus and capital flows)
- Backend field names preserved — zero database migration risk

### C2: Telegram 2.0 Three-Format System
- Refactored telegram_broadcast.py format_story_for_telegram()
- THE SETUP: 🔥/📈 header, alpha trigger, === TRADE PARAMETERS === (stop, target, invalidation)
- THE FLOW: 💹 header, === MEDIA vs CAPITAL ===, institutional bias
- THE PULSE: rapid-response heartbeat (unchanged in main())
- FALLBACK_FORMAT: SETUP↔FLOW rotation
- Hashtags: #EDGE_ALERT, #EDGE_ACTIVE, #EDGE_MONITOR

### Verified
- 146/146 tests passing
- Live CDN: lagazzettadikyiv.com renders Δ Edge throughout
- Sample THE SETUP dispatch: clean, actionable, professional
- All 5 P2/P3 bug fixes (from earlier) still active

## Pipeline Hardening — Completed (Jun 27)

### shipit.sh — Unified Deploy Wrapper
- 4-stage bash script: Build → Deploy HTML (no-cache) → Deploy JSON (no-store) → Static assets (1d cache)
- Cache-Control headers injected at upload time via `gsutil -h`
- Error handling: failures logged to /opt/gazzetta-di-kyiv/deploy_report.txt
- Replaces deploy_to_gcs.py in governor STEPS array
- Verified live headers:
  - index.html: `Cache-Control: public, max-age=0, must-revalidate` ✓
  - data/stories.json: `Cache-Control: private, no-store` ✓
  - data/flows.json: `Cache-Control: private, no-store` ✓

### Governor Update
- Deploy step now calls `bash scripts/shipit.sh` instead of `python deploy_to_gcs.py`
- rebuild_site EXEC command now includes shipit.sh deploy after build_frontend

### FRED Regime Classifier Fix
- Root cause: binary thresholds (5.5%/2.5%) couldn't capture 4.40% rate environment
- New multi-dimensional classifier: 7 regimes (INVERSION, RESTRICTIVE, TIGHTENING, NEUTRAL-TIGHT, STRESS, NEUTRAL, EASING, ACCOMMODATIVE)
- Uses: DGS10 (nominal) + DFII10 (real rate) + T10Y2Y (spread) + VIX + NFCI + UNRATE
- Current regime: **TIGHTENING** (10Y: 4.40%, real yield: 2.19%, curve un-inverted at +0.31bp)
- Was previously: NEUTRAL (stuck — the binary thresholds couldn't classify 4.40%)

## Remaining Known Issues

### P2 — Deferred
- FRED macro regime classifier stuck at "NEUTRAL"
- NMC data 26h stale (fetch_narrative_cap.py not in governor)
- Light-mode design refactor (~50 color changes)

### P3 — Minor
- broadcast_state.json permission issue on rsync (lock file)
- Some story-level tickers still use affected_tickers[0] (not narrative canonical)

## Strategic Direction

### Completed ✅
- CTO_STATE.md persistence protocol (this file)
- GAP → Δ Edge semantic transition
- Telegram 2.0 three-format system
- 5 P2/P3 UI fixes (threshold text, sidebar tickers, CFT guards, N/A display, radar dynamics)
- NMC expansion 57→67 assets

### Next Priorities
1. FRED classifier fix (unstick from NEUTRAL)
2. Move fetch_narrative_cap.py into governor for live NMC
3. Weekly NMC reassessment cadence
4. Light-mode design refactor
5. Thematic Portfolios (v2.0) — narrative cards → mini-portfolios

## Deployment Pattern (do NOT deviate)
1. Edit locally in ~/lagazzettadikyiv/
2. scp to gazzetta-prod:/tmp/
3. sudo mv to /opt/gazzetta-di-kyiv/scripts/ + chmod +x for .sh files
4. sudo find /opt/gazzetta-di-kyiv/scripts/__pycache__ -delete
5. Test: sudo bash scripts/shipit.sh (build + deploy with proper headers)
6. Verify Cache-Control: curl -sI https://storage.googleapis.com/www.lagazzettadikyiv.com/index.html | grep cache
7. git add + commit + push IMMEDIATELY
8. Never rely on governor's auto-deploy — shipit.sh is the single source of truth for deploys

## Critical Pitfalls (do NOT repeat)
- GCS index.html may NOT update via rsync — use direct `gsutil cp` if needed
- Google edge caching on storage.googleapis.com: requires cache-busting query params
- Governor timer overwrites manual repairs: stop timer before manual JSON repairs
- SQLite on VM: must use `sudo -u gazzetta sqlite3`
- API keys with shell-special chars: write to /tmp/file first
- Never pipe Python through SSH heredoc — bash interprets $ and {} in f-strings
- Use temp files (scp .py → /tmp/) for all VM Python execution
