#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# ARIA — Google Cloud one-time setup script
# Run once per project to provision all required GCP resources.
# Usage: bash setup-gcp.sh <YOUR_PROJECT_ID>
# ─────────────────────────────────────────────────────────────────────────────
set -euo pipefail

PROJECT_ID="${1:?Usage: bash setup-gcp.sh <PROJECT_ID>}"
REGION="us-central1"
REPO="aria"

echo "🚀 Setting up ARIA on project: $PROJECT_ID"

# 1. Set project
gcloud config set project "$PROJECT_ID"

# 2. Enable required APIs
echo "→ Enabling APIs..."
gcloud services enable \
  run.googleapis.com \
  cloudbuild.googleapis.com \
  artifactregistry.googleapis.com \
  aiplatform.googleapis.com \
  secretmanager.googleapis.com \
  firestore.googleapis.com \
  --project="$PROJECT_ID"

# 3. Create Artifact Registry repository
echo "→ Creating Artifact Registry repo..."
gcloud artifacts repositories create "$REPO" \
  --repository-format=docker \
  --location="$REGION" \
  --description="ARIA Docker images" \
  --project="$PROJECT_ID" 2>/dev/null || echo "   (already exists)"

# 4. Create Secret Manager secret for API key
echo "→ Creating secret for GOOGLE_API_KEY..."
gcloud secrets create aria-google-api-key \
  --replication-policy=automatic \
  --project="$PROJECT_ID" 2>/dev/null || echo "   (already exists)"

echo ""
echo "⚠️  Add your Gemini API key to Secret Manager:"
echo "   echo -n 'YOUR_API_KEY' | gcloud secrets versions add aria-google-api-key --data-file=-"
echo ""

# 5. Grant Cloud Build access to Secret Manager
CB_SA="$(gcloud projects describe $PROJECT_ID --format='value(projectNumber)')@cloudbuild.gserviceaccount.com"
echo "→ Granting Cloud Build SA access to secrets..."
gcloud secrets add-iam-policy-binding aria-google-api-key \
  --member="serviceAccount:$CB_SA" \
  --role="roles/secretmanager.secretAccessor" \
  --project="$PROJECT_ID"

# 6. Grant Cloud Build permission to deploy to Cloud Run
echo "→ Granting Cloud Build SA Cloud Run deploy permissions..."
gcloud projects add-iam-policy-binding "$PROJECT_ID" \
  --member="serviceAccount:$CB_SA" \
  --role="roles/run.admin"
gcloud projects add-iam-policy-binding "$PROJECT_ID" \
  --member="serviceAccount:$CB_SA" \
  --role="roles/iam.serviceAccountUser"

echo ""
echo "✅ GCP setup complete!"
echo ""
echo "Next steps:"
echo "  1. Add your Gemini API key:"
echo "     echo -n 'YOUR_KEY' | gcloud secrets versions add aria-google-api-key --data-file=-"
echo ""
echo "  2. Connect your repo to Cloud Build and trigger a build:"
echo "     gcloud builds submit --config=cloudbuild.yaml --project=$PROJECT_ID"
echo ""
echo "  3. Or run locally:"
echo "     cp backend/.env.example backend/.env  # fill in your keys"
echo "     docker compose up --build"
