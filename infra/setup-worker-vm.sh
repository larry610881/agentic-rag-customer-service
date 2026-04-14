#!/bin/bash
# === Setup arq Worker on VM ===
# 在 VM 上直接用 uv 跑 arq worker（不需要 Docker/podman）
#
# 執行方式：
#   1. gcloud compute ssh db-services --zone=asia-east1-b --tunnel-through-iap
#   2. bash setup-worker-vm.sh

set -e

REPO_DIR="$HOME/agentic-rag-backend"
REPO_URL="https://github.com/larry610881/agentic-rag-customer-service.git"

echo "=== 1. Install uv ==="
if ! command -v uv &> /dev/null; then
  curl -LsSf https://astral.sh/uv/install.sh | sh
  export PATH="$HOME/.local/bin:$PATH"
fi

echo "=== 2. Clone/update repo ==="
if [ -d "$REPO_DIR" ]; then
  cd "$REPO_DIR"
  git pull origin main
else
  git clone --depth 1 "$REPO_URL" "$REPO_DIR"
  cd "$REPO_DIR"
fi

echo "=== 3. Install dependencies ==="
cd apps/backend
uv sync --frozen --no-dev

echo "=== 4. Create env file ==="
cat > .env << 'ENVEOF'
DATABASE_URL_OVERRIDE=postgresql+asyncpg://postgres:1qaz@WSX3edc@127.0.0.1:5432/agentic_rag
REDIS_URL_OVERRIDE=redis://default:1qaz@WSX3edc@127.0.0.1:6379
MILVUS_URI=http://127.0.0.1:19530
STORAGE_BACKEND=gcs
GCS_BUCKET_NAME=agentic-rag-cs-documents
ENCRYPTION_MASTER_KEY=f88253402ac557139c6d51b124356e135e86e6536050263dd8a0eb623f17854a
APP_ENV=production
LOG_LEVEL=INFO
ENVEOF

echo "=== 5. Create systemd service ==="
sudo tee /etc/systemd/system/arq-worker.service > /dev/null << 'SVCEOF'
[Unit]
Description=arq Worker - Agentic RAG Background Tasks
After=network.target

[Service]
Type=simple
User=p10359945
WorkingDirectory=/home/p10359945/agentic-rag-backend/apps/backend
ExecStart=/home/p10359945/agentic-rag-backend/apps/backend/.venv/bin/arq src.worker.WorkerSettings
Restart=always
RestartSec=5
EnvironmentFile=/home/p10359945/agentic-rag-backend/apps/backend/.env

[Install]
WantedBy=multi-user.target
SVCEOF

echo "=== 6. Start worker ==="
sudo systemctl daemon-reload
sudo systemctl enable arq-worker
sudo systemctl restart arq-worker

echo ""
echo "=== Done! ==="
sudo systemctl status arq-worker --no-pager
echo ""
echo "Commands:"
echo "  sudo systemctl status arq-worker"
echo "  sudo journalctl -u arq-worker -f"
echo "  sudo systemctl restart arq-worker"
