#!/bin/bash
# === VM 重建腳本 ===
# 在 GCP VM (db-services) 上執行
# SSH: gcloud compute ssh db-services --zone=asia-east1-b --tunnel-through-iap --project=project-4dc6cadb-5d47-4482-a32

set -e

echo "=== 1. 停止並移除舊容器 ==="
podman stop qdrant redis postgres 2>/dev/null || true
podman rm qdrant redis postgres 2>/dev/null || true

echo "=== 2. 清除舊 volumes ==="
podman volume rm pgdata qdrant_storage redis_data 2>/dev/null || true

echo "=== 3. 建立新 volumes ==="
podman volume create pgdata
podman volume create redis_data
podman volume create etcd_data
podman volume create minio_data
podman volume create milvus_data

echo "=== 4. 啟動 PostgreSQL ==="
podman run -d --name postgres \
  --restart=unless-stopped \
  -p 5432:5432 \
  -e POSTGRES_USER=postgres \
  -e POSTGRES_PASSWORD=postgres \
  -e POSTGRES_DB=agentic_rag \
  -v pgdata:/var/lib/postgresql/data \
  docker.io/library/postgres:16-alpine

echo "=== 5. 啟動 Redis ==="
podman run -d --name redis \
  --restart=unless-stopped \
  -p 6379:6379 \
  -v redis_data:/data \
  docker.io/library/redis:7-alpine

echo "=== 6. 啟動 etcd（Milvus 依賴）==="
podman run -d --name etcd \
  --restart=unless-stopped \
  -p 2379:2379 \
  -e ETCD_AUTO_COMPACTION_MODE=revision \
  -e ETCD_AUTO_COMPACTION_RETENTION=1000 \
  -e ETCD_QUOTA_BACKEND_BYTES=4294967296 \
  -e ETCD_SNAPSHOT_COUNT=50000 \
  -v etcd_data:/etcd \
  quay.io/coreos/etcd:v3.5.18 \
  etcd -advertise-client-urls=http://127.0.0.1:2379 -listen-client-urls http://0.0.0.0:2379 --data-dir /etcd

echo "=== 7. 啟動 MinIO（Milvus 依賴）==="
podman run -d --name minio \
  --restart=unless-stopped \
  -p 9000:9000 -p 9001:9001 \
  -e MINIO_ACCESS_KEY=minioadmin \
  -e MINIO_SECRET_KEY=minioadmin \
  -v minio_data:/minio_data \
  docker.io/minio/minio:RELEASE.2024-11-07T00-52-20Z \
  server /minio_data --console-address ":9001"

echo "等待 etcd + minio 啟動..."
sleep 10

echo "=== 8. 啟動 Milvus ==="
podman run -d --name milvus \
  --restart=unless-stopped \
  --network=host \
  -e ETCD_ENDPOINTS=127.0.0.1:2379 \
  -e MINIO_ADDRESS=127.0.0.1:9000 \
  -v milvus_data:/var/lib/milvus \
  docker.io/milvusdb/milvus:v2.5.6 \
  milvus run standalone

echo "等待所有服務就緒..."
sleep 15

echo "=== 9. 驗證服務 ==="
podman exec postgres pg_isready -U postgres && echo "✓ PostgreSQL OK" || echo "✗ PostgreSQL FAILED"
podman exec redis redis-cli ping && echo "✓ Redis OK" || echo "✗ Redis FAILED"
curl -sf http://localhost:9091/healthz && echo "✓ Milvus OK" || echo "✗ Milvus FAILED"

echo ""
echo "=== 完成！==="
echo "PostgreSQL: localhost:5432 (agentic_rag)"
echo "Redis: localhost:6379"
echo "Milvus: localhost:19530"
echo ""
echo "下一步：從 Cloud Run backend 連上後，SQLAlchemy create_all 會自動建表"
