#!/bin/bash
# === 在 VM 上安裝 Docker CE（Ubuntu 24.04）===
# 執行前假設：已登入 VM，具備 sudo 權限

set -euo pipefail

echo "=== 1. 移除舊版 Docker 套件（若有）==="
for pkg in docker.io docker-doc docker-compose docker-compose-v2 podman-docker containerd runc; do
  sudo apt-get remove -y "$pkg" 2>/dev/null || true
done

echo "=== 2. 設定 Docker 官方 apt repo ==="
sudo apt-get update
sudo apt-get install -y ca-certificates curl gnupg lsb-release

sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | \
  sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
sudo chmod a+r /etc/apt/keyrings/docker.gpg

echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] \
  https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" | \
  sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

echo "=== 3. 安裝 Docker Engine ==="
sudo apt-get update
sudo apt-get install -y \
  docker-ce \
  docker-ce-cli \
  containerd.io \
  docker-buildx-plugin \
  docker-compose-plugin

echo "=== 4. 啟用 Docker 服務 + 加入 group ==="
sudo systemctl enable --now docker
sudo usermod -aG docker "$USER"

echo "=== 5. 驗證 ==="
docker --version
docker compose version
echo ""
echo "✓ Docker 安裝完成。"
echo "⚠ 需重新登入（logout & login）才能讓 docker group 生效，或執行：newgrp docker"
