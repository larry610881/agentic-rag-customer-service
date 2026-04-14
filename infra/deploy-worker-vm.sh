#!/bin/bash
# === Deploy arq Worker to VM ===
# 在 GCP VM (db-services) 上用 podman 跑 arq worker
#
# 前置：已 push backend image 到 Artifact Registry
# 用法：bash infra/deploy-worker-vm.sh

set -e

PROJECT_ID="project-4dc6cadb-5d47-4482-a32"
REGION="asia-east1"
REPO="asia-east1-docker.pkg.dev/${PROJECT_ID}/cloud-run-source-deploy"
IMAGE_TAG="${1:-latest}"

# Get latest backend image tag from Cloud Run
if [ "$IMAGE_TAG" = "latest" ]; then
  IMAGE_TAG=$(gcloud run services describe agentic-rag --region=$REGION --format='value(spec.template.spec.containers[0].image)' | grep -o '[^:]*$')
  echo "Using backend image tag: ${IMAGE_TAG}"
fi

FULL_IMAGE="${REPO}/agentic-rag:${IMAGE_TAG}"
echo "Image: ${FULL_IMAGE}"

# SSH into VM and deploy
gcloud compute ssh db-services --zone=asia-east1-b --tunnel-through-iap --command="
set -e

# Stop old worker
podman stop arq-worker 2>/dev/null || true
podman rm arq-worker 2>/dev/null || true

# Pull latest image (need to auth with gcloud)
# Note: VM needs Artifact Registry read access
podman pull ${FULL_IMAGE} 2>/dev/null || {
  echo 'Pull failed — trying with gcloud auth...'
  gcloud auth configure-docker ${REGION}-docker.pkg.dev --quiet 2>/dev/null
  podman pull ${FULL_IMAGE}
}

# Run worker
podman run -d --name arq-worker \\
  --restart=unless-stopped \\
  --network=host \\
  -e DATABASE_URL_OVERRIDE='postgresql+asyncpg://postgres:1qaz@WSX3edc@127.0.0.1:5432/agentic_rag' \\
  -e REDIS_URL_OVERRIDE='redis://default:1qaz@WSX3edc@127.0.0.1:6379' \\
  -e MILVUS_URI='http://127.0.0.1:19530' \\
  -e STORAGE_BACKEND=gcs \\
  -e GCS_BUCKET_NAME=agentic-rag-cs-documents \\
  -e APP_ENV=production \\
  -e LOG_LEVEL=INFO \\
  -e PYTHONPATH=/app \\
  ${FULL_IMAGE} \\
  .venv/bin/arq src.worker.WorkerSettings

echo ''
echo '=== Worker deployed ==='
podman ps --filter name=arq-worker
"
