#!/usr/bin/env bash
# check-task.sh — TaskCompleted hook
# 在 Agent 完成任務後，自動檢查測試是否通過

set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")/../.." && pwd)"

echo "🔍 檢查測試狀態..."

# 檢查後端測試（如果 apps/backend 存在）
if [ -d "$PROJECT_DIR/apps/backend" ] && [ -f "$PROJECT_DIR/apps/backend/pyproject.toml" ]; then
  echo "▶ 後端測試..."
  cd "$PROJECT_DIR/apps/backend"
  if uv run python -m pytest tests/ -v --tb=short -q 2>&1; then
    echo "✅ 後端測試通過"
  else
    echo "❌ 後端測試失敗"
    exit 1
  fi
fi

# 檢查前端測試（如果 apps/frontend 存在）
if [ -d "$PROJECT_DIR/apps/frontend" ] && [ -f "$PROJECT_DIR/apps/frontend/package.json" ]; then
  echo "▶ 前端測試..."
  cd "$PROJECT_DIR/apps/frontend"
  if npx vitest run --reporter=verbose 2>&1; then
    echo "✅ 前端測試通過"
  else
    echo "❌ 前端測試失敗"
    exit 1
  fi
fi

echo "✅ 所有測試通過"
