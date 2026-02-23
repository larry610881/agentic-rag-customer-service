#!/usr/bin/env bash
# check-idle.sh — TeammateIdle hook
# 在 Agent 閒置前，檢查是否有未 commit 的變更

set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$PROJECT_DIR"

# 檢查是否有未 commit 的變更
CHANGES=$(git status --porcelain 2>/dev/null | head -20)

if [ -n "$CHANGES" ]; then
  echo "⚠️ 偵測到未 commit 的變更："
  echo "$CHANGES"
  echo ""
  echo "建議：在閒置前 commit 目前的進度，避免工作遺失。"
  echo "  git add -A && git commit -m 'wip: [描述當前進度]'"
fi
