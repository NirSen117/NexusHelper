#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 1 ]]; then
  echo "Usage: $0 <nexushelper-gcp-project-id> [region]" >&2
  exit 2
fi

PROJECT_ID="$1"
REGION="${2:-us-central1}"
SERVICE_ACCOUNT="nexushelper-runtime@${PROJECT_ID}.iam.gserviceaccount.com"

if ! gcloud auth list --filter=status:ACTIVE --format='value(account)' 2>/dev/null | grep -q .; then
  echo "No active gcloud account. Run: gcloud auth login" >&2
  exit 1
fi
if [[ -z "${FALKORDB_HOST:-}" ]]; then
  echo "Set FALKORDB_HOST to a private, reachable FalkorDB endpoint before deployment." >&2
  exit 1
fi

echo "Deploying NexusHelper API to project ${PROJECT_ID}, region ${REGION}."
echo "This uses the dedicated runtime identity ${SERVICE_ACCOUNT}."
gcloud run deploy nexushelper-api \
  --project "$PROJECT_ID" \
  --region "$REGION" \
  --source . \
  --service-account "$SERVICE_ACCOUNT" \
  --allow-unauthenticated \
  --memory 1Gi \
  --cpu 2 \
  --set-env-vars "^~^APP_ENV=production~DEMO_AUTH_ENABLED=false~FIREBASE_AUTH_ENABLED=true~FIREBASE_PROJECT_ID=${PROJECT_ID}~FIRESTORE_PROJECT_ID=${PROJECT_ID}~PROFILE_STORE=firestore~MODEL_PROVIDER=groq~FRONTEND_ORIGIN=https://${PROJECT_ID}.web.app~FALKORDB_HOST=${FALKORDB_HOST}~FALKORDB_PORT=${FALKORDB_PORT:-6379}~FALKORDB_USERNAME=${FALKORDB_USERNAME:-}~FALKORDB_USE_TLS=${FALKORDB_USE_TLS:-true}" \
  --set-secrets "GROQ_API_KEY=groq-api-key:latest,FALKORDB_PASSWORD=falkordb-password:latest"
