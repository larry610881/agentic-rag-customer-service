# Configuration

完整的環境變數與 Provider 設定指南。

## 環境變數檔案

| 檔案 | 用途 |
|------|------|
| `apps/backend/.env` | 後端環境變數 |
| `apps/frontend/.env.local` | 前端環境變數 |
| `.env` | Docker Compose 共用 |

所有 `.env` 檔案已加入 `.gitignore`，禁止提交至版控。

## 環境變數清單

### Database

| 變數 | 預設值 | 說明 |
|------|--------|------|
| `POSTGRES_USER` | `postgres` | PostgreSQL 使用者 |
| `POSTGRES_PASSWORD` | `postgres` | PostgreSQL 密碼 |
| `POSTGRES_HOST` | `localhost` | PostgreSQL 主機 |
| `POSTGRES_PORT` | `5432` | PostgreSQL 埠號 |
| `POSTGRES_DB` | `agentic_rag` | 資料庫名稱 |
| `REDIS_HOST` | `localhost` | Redis 主機 |
| `REDIS_PORT` | `6379` | Redis 埠號 |

### Milvus (Vector DB)

| 變數 | 預設值 | 說明 |
|------|--------|------|
| `MILVUS_HOST` | `localhost` | Milvus 主機 |
| `MILVUS_PORT` | `19530` | Milvus gRPC 埠號 |

### Embedding

| 變數 | 預設值 | 說明 |
|------|--------|------|
| `EMBEDDING_PROVIDER` | `fake` | Provider：`fake` \| `openai` \| `qwen` |
| `EMBEDDING_MODEL` | `text-embedding-3-large` | Embedding 模型名稱（2026-04 升級） |
| `EMBEDDING_VECTOR_SIZE` | `3072` | 向量維度（隨模型升級，全系統統一） |
| `EMBEDDING_BASE_URL` | (auto) | 自訂 base URL（留空自動偵測） |

### LLM

| 變數 | 預設值 | 說明 |
|------|--------|------|
| `LLM_MAX_TOKENS` | `1024` | 最大輸出 token 數 |

> LLM Provider 由資料庫 `ProviderSetting` 動態驅動，無需環境變數設定。

### E2E 測試

| 變數 | 預設值 | 說明 |
|------|--------|------|
| `E2E_MODE` | `false` | 設為 `true` 時啟用 FakeLLM + MetaSupervisor（無真實 LLM 呼叫） |

### API Keys

| 變數 | 用於 |
|------|------|
| `OPENAI_API_KEY` | OpenAI Embedding & LLM |
| `ANTHROPIC_API_KEY` | Anthropic LLM |
| `QWEN_API_KEY` | Qwen (DashScope) Embedding & LLM |
| `OPENROUTER_API_KEY` | OpenRouter LLM |

> `OPENAI_CHAT_API_KEY` 仍可使用（向下相容），但建議改用 `OPENAI_API_KEY`。

### LINE Bot

| 變數 | 說明 |
|------|------|
| `LINE_CHANNEL_SECRET` | LINE Channel Secret |
| `LINE_CHANNEL_ACCESS_TOKEN` | LINE Channel Access Token |
| `LINE_DEFAULT_TENANT_ID` | LINE 預設租戶 ID |
| `LINE_DEFAULT_KB_ID` | LINE 預設知識庫 ID |

### RAG

| 變數 | 預設值 | 說明 |
|------|--------|------|
| `RAG_SCORE_THRESHOLD` | `0.3` | 向量搜尋最低分數門檻 |
| `RAG_TOP_K` | `5` | 檢索結果數量 |

### Pricing

| 變數 | 格式 |
|------|------|
| `LLM_PRICING_JSON` | `{"model": {"input": price_per_1m, "output": price_per_1m}}` |

## Provider 設定

> LLM Provider 現由資料庫 `ProviderSetting` 動態管理（後台 UI 設定），不再需要環境變數。
> 以下範例僅適用於 **Embedding Provider**（仍為 env-based）。

### Embedding 範例

```env
# OpenAI Embedding
EMBEDDING_PROVIDER=openai
OPENAI_API_KEY=sk-xxx
EMBEDDING_MODEL=text-embedding-3-small

# Qwen Embedding
EMBEDDING_PROVIDER=qwen
QWEN_API_KEY=sk-your-dashscope-key
EMBEDDING_MODEL=text-embedding-v3
```

DashScope 國際站：https://dashscope-intl.aliyuncs.com/compatible-mode/v1

## E2E 測試模式

```bash
# 啟動後端（FakeLLM + MetaSupervisor，無需真實 API Key）
E2E_MODE=true uv run uvicorn src.main:app --port 8000
```
