#!/usr/bin/env bash
# ops/setup_newsletter.sh
#
# One-shot setup script for the newsletter intelligence harvester.
# Run this ONCE from your local machine (after running gmail_oauth_setup.py).
#
# Usage:
#   bash ops/setup_newsletter.sh
#
# Prerequisites:
#   - gcloud CLI authenticated as solyaninalexander@gmail.com
#   - .gmail_token.json exists in project root (from gmail_oauth_setup.py)

set -euo pipefail

PROJECT_ID="project-b7155ed8-61c1-491f-a36"
REGION="us-central1"
SERVICE_NAME="gazzetta-newsletter-harvester"
SERVICE_ACCOUNT="newsletter-harvester@${PROJECT_ID}.iam.gserviceaccount.com"
SECRET_NAME="gmail-newsletter-token"
SCHEDULER_JOB="gazzetta-newsletters-daily"
SCHEDULER_SCHEDULE="0 7 * * *"  # 07:00 UTC daily = 10:00 Kyiv time

echo "═══════════════════════════════════════════════════════════"
echo " Gazzetta di Kyiv — Newsletter Harvester Setup"
echo " Project: ${PROJECT_ID}"
echo "═══════════════════════════════════════════════════════════"
echo ""

# ── Step 1: Enable required APIs ─────────────────────────────────────────────
echo "▶ [1/7] Enabling APIs..."
gcloud services enable \
    gmail.googleapis.com \
    secretmanager.googleapis.com \
    run.googleapis.com \
    cloudscheduler.googleapis.com \
    artifactregistry.googleapis.com \
    --project="${PROJECT_ID}"
echo "   ✓ APIs enabled"

# ── Step 2: Create service account ───────────────────────────────────────────
echo ""
echo "▶ [2/7] Creating service account..."
if gcloud iam service-accounts describe "${SERVICE_ACCOUNT}" --project="${PROJECT_ID}" &>/dev/null; then
    echo "   ✓ Service account already exists: ${SERVICE_ACCOUNT}"
else
    gcloud iam service-accounts create newsletter-harvester \
        --display-name="Newsletter Harvester" \
        --description="Service account for the Gazzetta newsletter intelligence harvester" \
        --project="${PROJECT_ID}"
    echo "   ✓ Created: ${SERVICE_ACCOUNT}"
fi

# ── Step 3: Grant Secret Manager access to service account ──────────────────
echo ""
echo "▶ [3/7] Granting Secret Manager access..."
gcloud projects add-iam-policy-binding "${PROJECT_ID}" \
    --member="serviceAccount:${SERVICE_ACCOUNT}" \
    --role="roles/secretmanager.secretAccessor" \
    --quiet
echo "   ✓ Granted roles/secretmanager.secretAccessor"

# ── Step 4: Store Gmail token in Secret Manager ──────────────────────────────
echo ""
echo "▶ [4/7] Storing Gmail OAuth token in Secret Manager..."
TOKEN_FILE="$(dirname "$0")/../.gmail_token.json"

if [ ! -f "${TOKEN_FILE}" ]; then
    echo "   ✗ ERROR: .gmail_token.json not found."
    echo "     Run first: python scripts/gmail_oauth_setup.py"
    exit 1
fi

if gcloud secrets describe "${SECRET_NAME}" --project="${PROJECT_ID}" &>/dev/null; then
    echo "   Updating existing secret..."
    gcloud secrets versions add "${SECRET_NAME}" \
        --data-file="${TOKEN_FILE}" \
        --project="${PROJECT_ID}"
else
    echo "   Creating new secret..."
    gcloud secrets create "${SECRET_NAME}" \
        --data-file="${TOKEN_FILE}" \
        --project="${PROJECT_ID}"
fi
echo "   ✓ Gmail token stored in Secret Manager as '${SECRET_NAME}'"

# Grant service account access to this specific secret
gcloud secrets add-iam-policy-binding "${SECRET_NAME}" \
    --member="serviceAccount:${SERVICE_ACCOUNT}" \
    --role="roles/secretmanager.secretAccessor" \
    --project="${PROJECT_ID}"
echo "   ✓ Service account granted access to secret"

# ── Step 5: Store DeepSeek key in Secret Manager (if not already there) ──────
echo ""
echo "▶ [5/7] Ensuring DeepSeek key is in Secret Manager..."
DEEPSEEK_SECRET="deepseek-api-key"

if gcloud secrets describe "${DEEPSEEK_SECRET}" --project="${PROJECT_ID}" &>/dev/null; then
    echo "   ✓ DeepSeek secret already exists"
else
    if [ -z "${DEEPSEEK_API_KEY:-}" ]; then
        # Try to read from local .env
        if [ -f "$(dirname "$0")/../.env" ]; then
            DEEPSEEK_API_KEY=$(grep DEEPSEEK_API_KEY "$(dirname "$0")/../.env" | cut -d= -f2)
        fi
    fi
    if [ -n "${DEEPSEEK_API_KEY:-}" ]; then
        echo -n "${DEEPSEEK_API_KEY}" | gcloud secrets create "${DEEPSEEK_SECRET}" \
            --data-file=- \
            --project="${PROJECT_ID}"
        echo "   ✓ DeepSeek key stored in Secret Manager"
    else
        echo "   ⚠ DEEPSEEK_API_KEY not found — add it manually:"
        echo "     echo 'sk-your-key' | gcloud secrets create deepseek-api-key --data-file=- --project=${PROJECT_ID}"
    fi
fi

# Grant service account access to DeepSeek secret
gcloud secrets add-iam-policy-binding "${DEEPSEEK_SECRET}" \
    --member="serviceAccount:${SERVICE_ACCOUNT}" \
    --role="roles/secretmanager.secretAccessor" \
    --project="${PROJECT_ID}" 2>/dev/null || true

# ── Step 6: Build and deploy Cloud Run job ────────────────────────────────────
echo ""
echo "▶ [6/7] Building and deploying Cloud Run job..."
cd "$(dirname "$0")/.."

# Build the Docker image
IMAGE="gcr.io/${PROJECT_ID}/${SERVICE_NAME}:latest"

gcloud builds submit \
    --tag="${IMAGE}" \
    --project="${PROJECT_ID}" \
    --gcs-log-dir="gs://www.lagazzettadikyiv.com/build-logs" \
    .

echo "   ✓ Docker image built: ${IMAGE}"

# Deploy as Cloud Run Job (not a service — it runs and exits)
gcloud run jobs create "${SERVICE_NAME}" \
    --image="${IMAGE}" \
    --region="${REGION}" \
    --service-account="${SERVICE_ACCOUNT}" \
    --set-secrets="DEEPSEEK_API_KEY=${DEEPSEEK_SECRET}:latest,TELEGRAM_BOT_TOKEN=telegram-bot-token:latest,_TCH=telegram-home-channel:latest" \
    --set-env-vars="GAZZETTA_ENV=production,PYTHONUNBUFFERED=1" \
    --args="--telegram" \
    --memory="512Mi" \
    --cpu="1" \
    --max-retries="2" \
    --task-timeout="600s" \
    --project="${PROJECT_ID}" 2>/dev/null || \
gcloud run jobs update "${SERVICE_NAME}" \
    --image="${IMAGE}" \
    --region="${REGION}" \
    --service-account="${SERVICE_ACCOUNT}" \
    --set-secrets="DEEPSEEK_API_KEY=${DEEPSEEK_SECRET}:latest" \
    --set-env-vars="GAZZETTA_ENV=production,PYTHONUNBUFFERED=1" \
    --args="--telegram" \
    --memory="512Mi" \
    --cpu="1" \
    --max-retries="2" \
    --task-timeout="600s" \
    --project="${PROJECT_ID}"

echo "   ✓ Cloud Run job deployed: ${SERVICE_NAME}"

# ── Step 7: Create Cloud Scheduler trigger ───────────────────────────────────
echo ""
echo "▶ [7/7] Setting up Cloud Scheduler (${SCHEDULER_SCHEDULE} = 10:00 Kyiv daily)..."

SCHEDULER_SA="newsletter-scheduler@${PROJECT_ID}.iam.gserviceaccount.com"

# Create scheduler service account if needed
if ! gcloud iam service-accounts describe "${SCHEDULER_SA}" --project="${PROJECT_ID}" &>/dev/null; then
    gcloud iam service-accounts create newsletter-scheduler \
        --display-name="Newsletter Scheduler" \
        --project="${PROJECT_ID}"
fi

# Grant scheduler SA permission to invoke Cloud Run jobs
gcloud projects add-iam-policy-binding "${PROJECT_ID}" \
    --member="serviceAccount:${SCHEDULER_SA}" \
    --role="roles/run.invoker" \
    --quiet

# Create or update the scheduler job
JOB_URI="https://${REGION}-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/${PROJECT_ID}/jobs/${SERVICE_NAME}:run"

if gcloud scheduler jobs describe "${SCHEDULER_JOB}" --location="${REGION}" --project="${PROJECT_ID}" &>/dev/null; then
    gcloud scheduler jobs update http "${SCHEDULER_JOB}" \
        --schedule="${SCHEDULER_SCHEDULE}" \
        --location="${REGION}" \
        --uri="${JOB_URI}" \
        --http-method="POST" \
        --oauth-service-account-email="${SCHEDULER_SA}" \
        --time-zone="UTC" \
        --project="${PROJECT_ID}"
    echo "   ✓ Scheduler job updated"
else
    gcloud scheduler jobs create http "${SCHEDULER_JOB}" \
        --schedule="${SCHEDULER_SCHEDULE}" \
        --location="${REGION}" \
        --uri="${JOB_URI}" \
        --http-method="POST" \
        --oauth-service-account-email="${SCHEDULER_SA}" \
        --time-zone="UTC" \
        --description="Daily newsletter intelligence harvest at 10:00 Kyiv time" \
        --project="${PROJECT_ID}"
    echo "   ✓ Scheduler job created"
fi

# ── Done ──────────────────────────────────────────────────────────────────────
echo ""
echo "═══════════════════════════════════════════════════════════"
echo " ✅ Setup complete!"
echo "═══════════════════════════════════════════════════════════"
echo ""
echo " Runs automatically every day at 10:00 Kyiv time (07:00 UTC)"
echo ""
echo " Manual trigger:"
echo "   gcloud run jobs execute ${SERVICE_NAME} --region=${REGION} --project=${PROJECT_ID}"
echo ""
echo " View logs:"
echo "   gcloud run jobs executions list --job=${SERVICE_NAME} --region=${REGION} --project=${PROJECT_ID}"
echo ""
echo " Output:"
echo "   data/newsletters.json (synced to GCS bucket)"
echo "   gazzetta.db → newsletters table"
echo "   Telegram digest → your _TCH channel"
echo ""
