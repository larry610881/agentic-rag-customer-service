#!/bin/bash
# === Cloud Run 部署腳本 ===
# 前置：gcloud auth login + gcloud auth configure-docker asia-east1-docker.pkg.dev
set -e

PROJECT_ID="project-4dc6cadb-5d47-4482-a32"
REGION="asia-east1"
REPO="asia-east1-docker.pkg.dev/${PROJECT_ID}/agentic-rag"

# --- 1. 確保 Artifact Registry repo 存在 ---
echo "=== 建立 Artifact Registry（如果不存在）==="
gcloud artifacts repositories describe agentic-rag \
  --location=$REGION --project=$PROJECT_ID 2>/dev/null || \
gcloud artifacts repositories create agentic-rag \
  --repository-format=docker \
  --location=$REGION \
  --project=$PROJECT_ID \
  --description="Agentic RAG Customer Service"

# --- 2. Build & Push Backend ---
echo ""
echo "=== Build Backend ==="
cd "$(dirname "$0")/../apps/backend"
docker build -t ${REPO}/backend:latest .
docker push ${REPO}/backend:latest

# --- 3. Build & Push MCP Server ---
echo ""
echo "=== Build Carrefour MCP ==="
cd "$(dirname "$0")/../mcp-servers/carrefour"
docker build -t ${REPO}/mcp-carrefour:latest .
docker push ${REPO}/mcp-carrefour:latest

# --- 4. Deploy Backend to Cloud Run ---
echo ""
echo "=== Deploy Backend to Cloud Run ==="
gcloud run deploy agentic-rag-backend \
  --image=${REPO}/backend:latest \
  --region=$REGION \
  --project=$PROJECT_ID \
  --platform=managed \
  --port=8000 \
  --memory=1Gi \
  --cpu=1 \
  --min-instances=0 \
  --max-instances=3 \
  --timeout=300 \
  --allow-unauthenticated \
  --set-env-vars="APP_ENV=production" \
  --env-vars-file=deploy-backend.env

# --- 5. Deploy MCP to Cloud Run ---
echo ""
echo "=== Deploy Carrefour MCP to Cloud Run ==="
gcloud run deploy agentic-rag-mcp-carrefour \
  --image=${REPO}/mcp-carrefour:latest \
  --region=$REGION \
  --project=$PROJECT_ID \
  --platform=managed \
  --port=8080 \
  --memory=256Mi \
  --cpu=1 \
  --min-instances=0 \
  --max-instances=2 \
  --timeout=30 \
  --allow-unauthenticated

echo ""
echo "=== 部署完成 ==="
BACKEND_URL=$(gcloud run services describe agentic-rag-backend --region=$REGION --project=$PROJECT_ID --format='value(status.url)')
MCP_URL=$(gcloud run services describe agentic-rag-mcp-carrefour --region=$REGION --project=$PROJECT_ID --format='value(status.url)')
echo "Backend: ${BACKEND_URL}"
echo "MCP: ${MCP_URL}/mcp"
echo ""
echo "下一步："
echo "1. 前端 VITE_API_URL 設為 ${BACKEND_URL}"
echo "2. 平台 MCP 工具庫註冊 ${MCP_URL}/mcp"
