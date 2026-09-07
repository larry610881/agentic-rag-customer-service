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

#### 推理強度（thinking）各供應商對應

Bot 的 `reasoning_effort`（`none` / `low` / `medium` / `high`，預設 `medium`）三通路共用，
但各供應商能接受的參數不同；不合法的組合一律丟棄（維持供應商預設）並記
`llm.reasoning_effort.dropped`，trace 的 `agent_llm` 節點以 `reasoning_effort_effective =
provider_default` 標示。對應表（`src/infrastructure/llm/`，2026-09-04 依 claude-api skill 核對）：

| 供應商 / 模型 | `none` | `low` / `medium` / `high` |
|---------------|--------|---------------------------|
| OpenAI gpt-5.x（agent 路徑必綁 function tools） | 直傳 `reasoning_effort=none` | **丟棄**（chat completions + tools 只收 `none`，2026-07-21 線上 400 實證） |
| OpenAI o-series | 直傳 | 直傳 |
| OpenAI gpt-4o 系（非 reasoning 模型） | 丟棄 | 丟棄 |
| Gemini（OpenAI 相容端點） | 直傳 `none` | 直傳（`minimal` → `low`） |
| Anthropic Opus 5 / Sonnet 5（省略即思考） | `thinking: {type: "disabled"}` | `thinking: {type: "adaptive"}` + `output_config.effort` |
| Anthropic Opus 4.6 / 4.7 / 4.8、Sonnet 4.6 | 不帶 `thinking`（省略 = 不思考） | `thinking: {type: "adaptive"}` + `output_config.effort` |
| Anthropic Fable 5 / Mythos 5（thinking 永遠開） | 丟棄（`disabled` 回 400） | `adaptive` + `output_config.effort` |
| Anthropic 更舊模型（3.x / 4 / 4.1 / 4.5、Haiku 4.5） | 不帶 `thinking` | 丟棄（不支援 adaptive / effort） |

推理 token：OpenAI `usage.completion_tokens_details.reasoning_tokens`、LangChain
`usage_metadata.output_token_details.reasoning` → 記入 trace 節點 `token_usage.reasoning_tokens`
與 trace `total_tokens.reasoning_tokens`、串流 `usage` 事件；Anthropic Messages API 不回傳
thinking token 明細（計入 `output_tokens`），故為 0。`token_usage_records` 無此欄位（不新增 migration）。

### 認證 / 安全（Issue #67）

| 變數 | 預設 | 說明 |
|------|------|------|
| `APP_ENV` | `production` | **預設 production（fail-closed）**：預設密鑰拒絕啟動、API docs 關閉、不接受無 `iss` 的舊票。本機開發請在 `.env` 明確設 `development` |
| `JWT_SECRET_KEY` | (dev fallback) | 非 development 必須覆寫 |
| `JWT_ISSUER` | `agentic-rag` | 所有票的 `iss` |
| `JWT_AUDIENCE` | `agentic-rag-api` | 所有票的 `aud` |
| `JWT_KEY_ID` | `k1` | JWT header `kid`；輪替 secret 時換值 |
| `JWT_ACCESS_TOKEN_EXPIRE_MINUTES` | `15` | 人類 access 票 |
| `JWT_REFRESH_TOKEN_EXPIRE_DAYS` | `7` | refresh 票（每次換票旋轉） |
| `API_ACCESS_TOKEN_EXPIRE_SECONDS` | `900` | 機器票（client_credentials） |
| `WIDGET_TOKEN_EXPIRE_SECONDS` | `900` | widget 短效票 |
| `LOGIN_MAX_FAILURES` / `LOGIN_FAILURE_WINDOW_SECONDS` / `LOGIN_LOCKOUT_SECONDS` | `5` / `900` / `900` | 登入失敗鎖定 |

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
