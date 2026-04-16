#!/bin/bash
# === Podman → Docker 遷移腳本（保留資料）===
#
# 適用：在 GCP VM (db-services) 將現有 podman rootless 容器遷移到 docker，
#        並保留 PostgreSQL / Milvus / MinIO / etcd / Redis 的所有資料。
#
# 策略：
#   1. pg_dump 安全網（獨立備份 SQL，若 volume 搬遷失敗可還原）
#   2. 停 podman，把各 volume 打包成 tar
#   3. 安裝 Docker（若尚未安裝）
#   4. 建 docker volumes 並還原 tar 內容
#   5. 用 docker compose 啟動
#   6. 驗證
#
# 不會遷移 qdrant（已棄用）；會主動刪除 qdrant 容器 + volume
#
# 執行：
#   bash infra/migrate-podman-to-docker.sh            # 完整遷移
#   DRY_RUN=1 bash infra/migrate-podman-to-docker.sh  # 只檢查不動作

set -euo pipefail

DRY_RUN="${DRY_RUN:-0}"
BACKUP_DIR="${BACKUP_DIR:-$HOME/migrate-backup-$(date +%Y%m%d-%H%M%S)}"
COMPOSE_FILE="${COMPOSE_FILE:-$HOME/docker-compose.yml}"
VOLUMES=(pgdata redis_data etcd_data minio_data milvus_data)

run() {
  if [[ "$DRY_RUN" == "1" ]]; then
    echo "[DRY] $*"
  else
    echo "+ $*"
    eval "$@"
  fi
}

echo "========================================"
echo " Podman → Docker 遷移"
echo " BACKUP_DIR = $BACKUP_DIR"
echo " DRY_RUN    = $DRY_RUN"
echo "========================================"

# -------------------------------------------------------------
# 0. 前置檢查
# -------------------------------------------------------------
echo ""
echo "=== 0. 前置檢查 ==="
if ! command -v podman &>/dev/null; then
  echo "✗ podman 未安裝，無需遷移"
  exit 1
fi
podman ps --format '{{.Names}}' | grep -qE '^postgres$' || {
  echo "✗ 找不到 podman 容器 'postgres'，中止"
  exit 1
}
echo "✓ podman postgres 容器存在"

DISK_AVAIL_GB=$(df -BG --output=avail / | tail -1 | tr -d 'G ')
echo "  磁碟可用空間：${DISK_AVAIL_GB}G"
if [[ "$DISK_AVAIL_GB" -lt 5 ]]; then
  echo "✗ 磁碟不足 5G，無法安全備份。中止"
  exit 1
fi

# -------------------------------------------------------------
# 1. PostgreSQL dump（安全網）
# -------------------------------------------------------------
echo ""
echo "=== 1. PostgreSQL pg_dumpall 備份 ==="
run "mkdir -p '$BACKUP_DIR'"
run "podman exec postgres pg_dumpall -U postgres | gzip > '$BACKUP_DIR/pg_dumpall.sql.gz'"
run "ls -lh '$BACKUP_DIR/pg_dumpall.sql.gz'"

# -------------------------------------------------------------
# 2. 停 podman 容器（保 volume）
# -------------------------------------------------------------
echo ""
echo "=== 2. 停止所有 podman 容器 ==="
run "podman stop qdrant milvus etcd minio redis postgres 2>/dev/null || true"

# -------------------------------------------------------------
# 3. 打包 podman volumes 為 tar
# -------------------------------------------------------------
echo ""
echo "=== 3. 打包 podman volumes ==="
for vol in "${VOLUMES[@]}"; do
  if podman volume exists "$vol" 2>/dev/null; then
    MOUNT=$(podman volume inspect "$vol" --format '{{.Mountpoint}}')
    echo "  $vol → $BACKUP_DIR/${vol}.tar.gz (from $MOUNT)"
    run "sudo tar -czf '$BACKUP_DIR/${vol}.tar.gz' -C '$MOUNT' ."
  else
    echo "  ⚠ volume '$vol' 不存在，略過"
  fi
done

# -------------------------------------------------------------
# 4. 安裝 Docker（若尚未安裝）
# -------------------------------------------------------------
echo ""
echo "=== 4. 安裝 Docker ==="
if command -v docker &>/dev/null; then
  echo "✓ docker 已安裝：$(docker --version)"
else
  SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
  run "bash '$SCRIPT_DIR/install-docker.sh'"
  # docker group 生效
  if ! docker ps &>/dev/null; then
    echo "⚠ 需重新登入 shell 才能用 docker，或執行：newgrp docker"
    echo "  後續指令將用 sudo docker 繼續"
    DOCKER="sudo docker"
  else
    DOCKER="docker"
  fi
fi
DOCKER="${DOCKER:-docker}"

# -------------------------------------------------------------
# 5. 建 docker volumes + 還原 tar 內容
# -------------------------------------------------------------
echo ""
echo "=== 5. 建 docker volumes 並還原資料 ==="
for vol in "${VOLUMES[@]}"; do
  TAR="$BACKUP_DIR/${vol}.tar.gz"
  if [[ ! -f "$TAR" ]]; then
    echo "  ⚠ 找不到 $TAR，略過"
    continue
  fi
  run "$DOCKER volume create '$vol' >/dev/null"
  # 用臨時 container 把 tar 解壓進去（避免 host 端需要 root 對應 uid）
  run "$DOCKER run --rm -v '${vol}':/restore -v '$BACKUP_DIR':/backup:ro alpine \
    sh -c 'cd /restore && tar -xzf /backup/${vol}.tar.gz'"
  echo "  ✓ $vol 還原完成"
done

# -------------------------------------------------------------
# 6. 啟動 docker compose
# -------------------------------------------------------------
echo ""
echo "=== 6. 啟動 docker compose ==="
if [[ ! -f "$COMPOSE_FILE" ]]; then
  echo "✗ 找不到 $COMPOSE_FILE"
  echo "  請將 infra/docker-compose.yml 上傳到 VM 後重跑，或設 COMPOSE_FILE 環境變數"
  exit 1
fi
run "cd \"\$(dirname '$COMPOSE_FILE')\" && $DOCKER compose -f '$COMPOSE_FILE' up -d"

echo ""
echo "等待服務就緒（60s）..."
run "sleep 60"

# -------------------------------------------------------------
# 7. 驗證
# -------------------------------------------------------------
echo ""
echo "=== 7. 驗證 ==="
run "$DOCKER ps --format 'table {{.Names}}\t{{.Image}}\t{{.Status}}'"
run "$DOCKER exec agentic-rag-db pg_isready -U postgres && echo '✓ PostgreSQL OK' || echo '✗ PostgreSQL FAILED'"
run "$DOCKER exec agentic-rag-redis redis-cli ping && echo '✓ Redis OK' || echo '✗ Redis FAILED'"
run "curl -sf http://localhost:9091/healthz && echo '✓ Milvus OK' || echo '✗ Milvus FAILED'"

# 快速資料檢查
echo ""
echo "  PostgreSQL 資料檢查："
run "$DOCKER exec agentic-rag-db psql -U postgres -d agentic_rag -c 'SELECT COUNT(*) AS tenants FROM tenants; SELECT COUNT(*) AS kbs FROM knowledge_bases; SELECT COUNT(*) AS docs FROM documents;'"

# -------------------------------------------------------------
# 8. 清 qdrant 殘留（已不使用）
# -------------------------------------------------------------
echo ""
echo "=== 8. 清 qdrant 殘留 ==="
run "podman rm -f qdrant 2>/dev/null || true"
run "podman volume rm qdrant_data 2>/dev/null || true"
echo "✓ qdrant 容器與 volume 已移除"

# -------------------------------------------------------------
# 9. 結束
# -------------------------------------------------------------
echo ""
echo "========================================"
echo " 遷移完成"
echo "========================================"
echo "備份位置：$BACKUP_DIR"
echo "  - pg_dumpall.sql.gz  （SQL dump 安全網）"
echo "  - *.tar.gz           （各 volume 原始快照）"
echo ""
echo "下一步："
echo "  1. 驗證 backend 連線正常（Cloud Run 應可以打 DB/Milvus）"
echo "  2. 驗證前端功能（登入、知識庫列表）"
echo "  3. 確認無誤後，可移除 podman："
echo "     podman rm -af; podman volume rm -af; sudo apt-get remove -y podman"
echo "  4. 一切正常後刪 $BACKUP_DIR 釋放磁碟（建議至少保留 24h）"
