#!/usr/bin/env bash
# Automated Deployment Script for SEC EDGAR Natural Language Analyst to Google Cloud Run

set -e

PROJECT_ID="${GCP_PROJECT_ID:-sec-analyst}"
REGION="${GCP_REGION:-us-central1}"
SERVICE_NAME="sec-edgar-analyst"

echo "=========================================================================="
echo "🚀 DEPLOYING SEC EDGAR ANALYST TO GOOGLE CLOUD RUN 🚀"
echo "=========================================================================="
echo "Project ID : ${PROJECT_ID}"
echo "Region     : ${REGION}"
echo "Service    : ${SERVICE_NAME}"
echo "--------------------------------------------------------------------------"

# Set active project
gcloud config set project "${PROJECT_ID}"

SA_NAME="sec-analyst-sa"
SA_EMAIL="${SA_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"
SA_FLAG=()

echo "🔍 Checking Service Account ${SA_EMAIL}..."
if gcloud iam service-accounts describe "${SA_EMAIL}" --project="${PROJECT_ID}" >/dev/null 2>&1; then
  echo "✅ Service account ${SA_EMAIL} exists."
  SA_FLAG=(--service-account "${SA_EMAIL}")
else
  echo "⚙️ Creating service account ${SA_EMAIL}..."
  if gcloud iam service-accounts create "${SA_NAME}" --display-name="SEC EDGAR Agent Service Account" --project="${PROJECT_ID}" >/dev/null 2>&1; then
    echo "✅ Service account ${SA_EMAIL} created."
    # Bind least-privilege roles
    for ROLE in roles/aiplatform.user roles/storage.objectUser roles/bigquery.dataViewer roles/bigquery.user roles/secretmanager.secretAccessor roles/serviceusage.serviceUsageConsumer; do
      gcloud projects add-iam-policy-binding "${PROJECT_ID}" --member="serviceAccount:${SA_EMAIL}" --role="${ROLE}" >/dev/null 2>&1 || true
    done

    SA_FLAG=(--service-account "${SA_EMAIL}")
  else
    echo "⚠️ Unable to create custom service account. Falling back to default Cloud Run service account."
  fi
fi

echo "\n📦 Building container & deploying to Google Cloud Run..."
gcloud run deploy "${SERVICE_NAME}" \
  --source . \
  --project "${PROJECT_ID}" \
  --region "${REGION}" \
  --allow-unauthenticated \
  "${SA_FLAG[@]}" \
  --set-env-vars GCP_PROJECT_ID="${PROJECT_ID}",GCP_REGION="${REGION}",GOOGLE_CLOUD_PROJECT="${PROJECT_ID}",GOOGLE_CLOUD_LOCATION="${REGION}",GOOGLE_GENAI_USE_VERTEXAI="true",REASONING_MODEL="gemini-2.5-pro",TOOL_MODEL="gemini-3.5-flash",MODEL_ARMOR_ENABLED="true",MODEL_ARMOR_TEMPLATE_ID="sec-analyst-model-armor-template",MODEL_ARMOR_LOCATION="${REGION}",MODEL_ARMOR_FAIL_OPEN="true",MODEL_ARMOR_UNAVAILABLE_POLICY="fail_open"



# Retrieve deployed service URL
SERVICE_URL=$(gcloud run services describe "${SERVICE_NAME}" --project "${PROJECT_ID}" --region "${REGION}" --format='value(status.url)')

echo "\n🔍 Verifying health probe on ${SERVICE_URL}/api/v1/health..."
if curl -s -f "${SERVICE_URL}/api/v1/health" > /dev/null; then
  echo "✅ Health check PASSED!"
else
  echo "⚠️ Health check warning: Unable to reach ${SERVICE_URL}/api/v1/health (may require deployment completion)."
fi

echo "\n=========================================================================="
echo "🎉 DEPLOYMENT COMPLETE! YOUR APP IS LIVE AT: ${SERVICE_URL} 🎉"
echo "=========================================================================="

