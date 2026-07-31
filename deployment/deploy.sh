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

echo "\n📦 Building container & deploying to Google Cloud Run..."
gcloud run deploy "${SERVICE_NAME}" \
  --source . \
  --project "${PROJECT_ID}" \
  --region "${REGION}" \
  --allow-unauthenticated \
  --set-env-vars GCP_PROJECT_ID="${PROJECT_ID}",GCP_REGION="${REGION}",REASONING_MODEL="gemini-2.5-pro",TOOL_MODEL="gemini-2.5-flash"

echo "\n=========================================================================="
echo "🎉 DEPLOYMENT COMPLETE! YOUR APP IS LIVE IN THE CLOUD 🎉"
echo "=========================================================================="
