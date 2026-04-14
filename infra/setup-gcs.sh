#!/bin/bash
# === GCS Bucket 建置 ===
set -e

PROJECT_ID="project-4dc6cadb-5d47-4482-a32"
BUCKET_NAME="agentic-rag-cs-documents"
REGION="asia-east1"

echo "=== 建立 GCS Bucket ==="
gcloud storage buckets create gs://${BUCKET_NAME} \
  --project=$PROJECT_ID \
  --location=$REGION \
  --default-storage-class=STANDARD \
  --uniform-bucket-level-access

echo "=== 設定 CORS（允許前端 signed URL 預覽）==="
cat > /tmp/cors.json << 'EOF'
[
  {
    "origin": ["*"],
    "method": ["GET", "HEAD"],
    "responseHeader": ["Content-Type", "Content-Disposition"],
    "maxAgeSeconds": 3600
  }
]
EOF
gcloud storage buckets update gs://${BUCKET_NAME} --cors-file=/tmp/cors.json

echo "=== 設定 lifecycle（可選：90 天後轉 Nearline）==="
cat > /tmp/lifecycle.json << 'EOF'
{
  "rule": [
    {
      "action": {"type": "SetStorageClass", "storageClass": "NEARLINE"},
      "condition": {"age": 90}
    }
  ]
}
EOF
gcloud storage buckets update gs://${BUCKET_NAME} --lifecycle-file=/tmp/lifecycle.json

echo ""
echo "=== GCS Bucket 建立完成 ==="
echo "Bucket: gs://${BUCKET_NAME}"
echo "Region: ${REGION}"
echo ""
echo "下一步："
echo "1. 後端 .env 設定 STORAGE_BACKEND=gcs"
echo "2. 後端 .env 設定 GCS_BUCKET_NAME=${BUCKET_NAME}"
echo "3. Cloud Run service account 需要 Storage Object Admin 權限"
echo "   gcloud projects add-iam-policy-binding ${PROJECT_ID} \\"
echo "     --member='serviceAccount:<CLOUD_RUN_SA>@${PROJECT_ID}.iam.gserviceaccount.com' \\"
echo "     --role='roles/storage.objectAdmin'"
