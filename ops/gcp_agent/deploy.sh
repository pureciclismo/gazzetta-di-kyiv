#!/usr/bin/env bash
set -e

# Deploy the Cloud Function
echo "Deploying gazzetta-content-agent to Google Cloud Functions (2nd Gen)..."

gcloud functions deploy gazzetta-content-agent \
  --gen2 \
  --runtime=python311 \
  --region=us-central1 \
  --source=. \
  --entry-point=process_intel \
  --trigger-http \
  --set-env-vars="GLM_API_KEY_1=3d76e17112094679a3236820eb5a3502.zX9w5hVuUqKu3pbL,GLM_API_KEY_2=0feba8763e0a4c808bbba55f5a02cd7e.7N3kvN7asehKbCZ3" \
  --set-secrets="DEEPSEEK_API_KEY=deepseek-api-key:latest" \
  --allow-unauthenticated

echo "Deployment complete."
