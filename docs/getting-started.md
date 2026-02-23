# Getting Started

5 分鐘快速啟動 Agentic RAG Customer Service 平台。

## Prerequisites

| 工具 | 版本 | 安裝 |
|------|------|------|
| Docker & Docker Compose | 24+ | [docker.com](https://docs.docker.com/get-docker/) |
| Python | 3.12+ | [python.org](https://www.python.org/) |
| uv | latest | `curl -LsSf https://astral.sh/uv/install.sh \| sh` |
| Node.js | 20+ | [nodejs.org](https://nodejs.org/) |
| Make | any | 系統內建 |

## Quick Start

### 1. Clone & Install

```bash
git clone https://github.com/larry610881/agentic-rag-customer-service.git
cd agentic-rag-customer-service
```

### 2. 啟動基礎服務

```bash
make dev-up
```

這會啟動 PostgreSQL、Redis、Qdrant 等依賴服務。

### 3. 設定環境變數

```bash
# 後端
cp apps/backend/.env.example apps/backend/.env
# 編輯 .env，至少設定一組 LLM Provider（或保留 fake 進行測試）
```

### 4. 安裝依賴

```bash
# 後端
cd apps/backend && uv sync && cd ../..

# 前端
cd apps/frontend && npm install && cd ../..
```

### 5. 資料庫初始化 & 種子資料

```bash
make seed-data
```

### 6. 執行測試

```bash
make test
```

所有測試應通過，確認環境正確。

### 7. 啟動開發伺服器

```bash
# 後端（預設 http://localhost:8000）
cd apps/backend && uv run uvicorn src.main:app --reload

# 前端（預設 http://localhost:3000）
cd apps/frontend && npm run dev
```

### 8. 開啟 Chat UI

瀏覽器開啟 `http://localhost:3000`，即可開始與 AI Agent 對話。

## 免費 LLM 快速體驗

使用 Qwen（通义千问）免費 API：

1. 前往 [DashScope](https://dashscope.console.aliyun.com/) 註冊取得 API Key
2. 設定 `.env`：

```env
LLM_PROVIDER=qwen
QWEN_API_KEY=sk-your-key
LLM_MODEL=qwen-plus
```

3. 重啟後端服務即可使用真實 LLM 回應。

## 下一步

- [Architecture](./architecture.md) — 了解 DDD 4-Layer + Multi-Agent 架構
- [Configuration](./configuration.md) — 完整 Provider 設定指南
- [API Reference](./api-reference.md) — 核心 API 端點
- [Demo Guide](./demo-guide.md) — 6 個 Demo 場景操作
