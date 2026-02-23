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

### Qdrant (Vector DB)

| 變數 | 預設值 | 說明 |
|------|--------|------|
| `QDRANT_HOST` | `localhost` | Qdrant 主機 |
| `QDRANT_REST_PORT` | `6333` | Qdrant REST 埠號 |
| `QDRANT_GRPC_PORT` | `6334` | Qdrant gRPC 埠號 |

### Embedding

| 變數 | 預設值 | 說明 |
|------|--------|------|
| `EMBEDDING_PROVIDER` | `fake` | Provider：`fake` \| `openai` \| `qwen` |
| `EMBEDDING_MODEL` | `text-embedding-3-small` | Embedding 模型名稱 |
| `EMBEDDING_VECTOR_SIZE` | `1536` | 向量維度 |
| `EMBEDDING_BASE_URL` | (auto) | 自訂 base URL（留空自動偵測） |

### LLM

| 變數 | 預設值 | 說明 |
|------|--------|------|
| `LLM_PROVIDER` | `fake` | Provider：`fake` \| `openai` \| `anthropic` \| `qwen` \| `openrouter` |
| `LLM_MODEL` | (per provider) | LLM 模型名稱 |
| `LLM_MAX_TOKENS` | `1024` | 最大輸出 token 數 |
| `LLM_BASE_URL` | (auto) | 自訂 base URL（留空自動偵測） |

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

## Provider 切換範例

### Qwen（免費）

```env
LLM_PROVIDER=qwen
QWEN_API_KEY=sk-your-dashscope-key
LLM_MODEL=qwen-plus

EMBEDDING_PROVIDER=qwen
EMBEDDING_MODEL=text-embedding-v3
```

DashScope 國際站：https://dashscope-intl.aliyuncs.com/compatible-mode/v1

### OpenAI

```env
LLM_PROVIDER=openai
OPENAI_API_KEY=sk-xxx
LLM_MODEL=gpt-4o

EMBEDDING_PROVIDER=openai
EMBEDDING_MODEL=text-embedding-3-small
```

### Anthropic

```env
LLM_PROVIDER=anthropic
ANTHROPIC_API_KEY=sk-ant-xxx
LLM_MODEL=claude-sonnet-4-20250514

# Anthropic 無 Embedding，搭配 OpenAI Embedding
EMBEDDING_PROVIDER=openai
OPENAI_API_KEY=sk-xxx
```

### OpenRouter

```env
LLM_PROVIDER=openrouter
OPENROUTER_API_KEY=sk-or-xxx
LLM_MODEL=openai/gpt-4o

# OpenRouter 無 Embedding，搭配其他 Embedding Provider
EMBEDDING_PROVIDER=openai
OPENAI_API_KEY=sk-xxx
```

### 混合使用

可自由搭配不同 Provider 的 Embedding 與 LLM：

```env
# 用 OpenAI Embedding + Qwen LLM（最省錢組合）
EMBEDDING_PROVIDER=openai
OPENAI_API_KEY=sk-xxx

LLM_PROVIDER=qwen
QWEN_API_KEY=sk-xxx
LLM_MODEL=qwen-plus
```

## Provider 預設值對照

| Provider | Default Model | Base URL |
|----------|---------------|----------|
| openai | gpt-4o | `https://api.openai.com/v1` |
| anthropic | claude-sonnet-4-20250514 | Anthropic 專用 |
| qwen | qwen-plus | `https://dashscope-intl.aliyuncs.com/compatible-mode/v1` |
| openrouter | openai/gpt-4o | `https://openrouter.ai/api/v1` |

## 自訂 Base URL

若需指向自建的 OpenAI 相容 API，可直接覆寫：

```env
LLM_PROVIDER=openai
LLM_BASE_URL=https://your-proxy.example.com/v1
OPENAI_API_KEY=sk-xxx
```
