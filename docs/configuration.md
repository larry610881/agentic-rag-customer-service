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

取樣參數（Issue #76，`reasoning_effort.sampling_params_allowed`，2026-09-07 依 claude-api skill
`shared/error-codes.md` / `shared/model-migration.md` 核對）：bot 的 `temperature` 只在模型接受時才送，
不接受時三條路徑（raw `_build_body`、`get_chat_model`、`react_agent_service._create_chat_model`）
一律不帶並記 `llm.temperature.dropped`（欄位 `model` / `param` / `requested`）；`top_p` / `top_k` 同規則。

| Anthropic 模型 | `temperature` / `top_p` / `top_k` |
|----------------|-----------------------------------|
| Opus 4.7 / 4.8、Opus 5、Fable 5 / 5.1、Mythos | **不送**（送任一即 400） |
| Sonnet 5 | **不送**（只收預設值，非預設 400） |
| Opus 4.6 / Sonnet 4.6、4.5 / 4.x / 3.x、未知模型 | 直傳 |

### OCR（Issue #78）

| 變數 | 預設值 | 說明 |
|------|--------|------|
| `OCR_DEFAULT_MODEL` | `anthropic:claude-sonnet-4-6` | 環境預設 OCR 引擎 spec；KB 與租戶都沒設定時使用 |
| `OCR_HYBRID_FULL_PAGE` | `true` | 混合模式（#82）：KB 有設切片格線（`ocr_slice_grid`，`2x3` / `3x2`）時，切片 OCR 之外再跑一次**整頁** OCR（同 prompt 家族、不帶切片前綴），以正規化商品名合併補回橫跨切片邊界被「半個商品直接省略」丟掉的 block。無切片格線或 `general` 模式不受影響；設 `false` 回到純切片 |
| `OCR_HYBRID_FULL_PAGE_MAX_SIDE` | `1600` | 混合模式整頁 pass 送模型前先等比縮到最長邊此像素數（省 token；整頁只負責補漏與頁面 markers，不需切片等級的字形解析度）。`0` = 不縮 |

**引擎**（`src/infrastructure/file_parser/ocr_engines/`，由 `DynamicOcrEngineFactory` 依 spec 建立、同 spec 共用實例）：

| spec 供應商 | 引擎 | 端點 | 備註 |
|-------------|------|------|------|
| `anthropic` | `ClaudeVisionOcrEngine`（Anthropic SDK） | Messages API | Sonnet 4.6 最穩；Haiku 4.5 曾有小幻覺 |
| `google` | `OpenAICompatVisionOcrEngine` | `https://generativelanguage.googleapis.com/v1beta/openai/chat/completions` | Gemini 3.7 Flash 較省（家樂福資料重建用）；頁面分類走 `response_format` json_schema |
| `openai` / `openrouter` / `litellm` | `OpenAICompatVisionOcrEngine` | 各自 `_BASE_URLS`（同 `llm_caller`） | 影像以 `image_url` data URL（base64，png / jpeg / webp 自動判斷）附上；prompt 額外加「不可補字、看不清楚留空、不得推測數字」 |

**spec 格式**：`provider:model`（例 `google:gemini-3.7-flash`）。無 `provider:` 前綴視為 `anthropic`；
空字串 = 未設定（沿用上層）。KB 建立 / 更新與租戶預設儲存時驗證供應商，不支援者回 400。

**優先序**：`KB.ocr_model` → 租戶 `default_ocr_model` → `OCR_DEFAULT_MODEL`；
reprocess 可用 `ocr_model` 參數覆寫本次（不寫回 KB）。API key 一律由 `DynamicLLMFactory.resolve_api_key`
解析（DB 加密設定優先，退回 `.env` 的 `<PROVIDER>_API_KEY`）；缺 key 或 401/403 時文件失敗訊息形如
`Gemini auth error: ...` / `Claude auth error: ...`。

用量記帳：每份文件各自累計（`OcrUsageTally`），`token_usage_records.model` 記實際 spec，
並行文件不互相污染（見 `docs/token-usage.md`）。

**混合模式合併規則**（`src/domain/knowledge/ocr_merge.py`，純邏輯；`sliced_ocr_helper.py` 負責並發呼叫）：
兩份輸出各解析為「頁面 `【marker】` + `===` block」；block 身分 = 商品名正規化（去空白 / 標點、
全形→半形、小寫）且相似度 ≥ 0.8（容忍一兩個字形差異，如 薈/著；350ml vs 600ml 仍視為不同）。
兩邊都有 → 保留**切片版**（字形較準）；只有整頁有 → 補進來（排在切片 block 之後）；
「商品：不詳」的整頁 block 不補。頁面 markers 切片為「不詳」時由整頁補上、切片有值以切片為準。
輸出格式與原 OCR 相同，`SeparatorTextSplitterService` 不需改動。

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

### Billing（Issue #74：雙軌計價 + 額度用盡策略）

計價相關設定**全部在資料庫 / 後台**，無環境變數：

| 層級 | 設定 | 位置 | 說明 |
|------|------|------|------|
| 方案 | `billing_mode` | `plans`（`/admin/plans`） | `token`（預設）或 `points`；token 永遠是事實來源，點數是記帳當下的換算層 |
| 方案 | `monthly_points` / `addon_pack_points` | `plans` | 點數制的每月基本點數 / 加購包點數；月費沿用 `base_price` |
| 方案 | `default_category_multiplier` + 倍率表 | `plans` + `plan_category_multipliers` | 用量類別 → 倍率（例：對話 1.0、精靈 0、評估 0.5）；未列類別用預設倍率；倍率 0 不扣點但仍記 token |
| 方案 | `exhaustion_policy` | `plans` | `auto_topup`（預設，額度用盡自動加購）或 `block`（用完即擋）；**獨立於計價模式** |
| 方案 | `tenant_may_change_policy` | `plans` | 租戶管理員能否自改策略（預設 false → `PUT /tenants/{id}/billing-policy` 回 403） |
| 方案 | `auto_topup_monthly_cap` | `plans` | 自動展延每月次數上限；`0` = 不限（預設） |
| 方案 | `grace_percent` | `plans` | `block` 策略的寬限百分比（以月基礎額度計）；預設 `0` |
| 方案 / 租戶 | `block_message` / `block_message_override` | `plans` / `tenants` | 被擋固定文案：租戶覆寫 → 方案 → 平台預設常數 |
| 租戶 | `exhaustion_policy_override` | `tenants` | `NULL` = 沿用方案 |
| 平台 | `usd_per_point` | `billing_settings`（`/admin/billing/settings`） | 1 點 = X USD；模型未設點數表時由美元換算；預設 `0.001` |
| 模型 | `points_per_1k_input` / `points_per_1k_output` | `model_pricing`（`PUT /admin/pricing/{id}`） | 模型點數表（每千 token；輸入側含 cache tokens）；優先於平台匯率 |

換算順序：模型點數表 → 否則 `ceil(cost_usd / usd_per_point)` → × 類別倍率 → 無條件進位。

用盡預檢：`QuotaPreflightService`（web / widget / LINE / 文件處理 / 評估跑批共用），
Redis 快取 30 秒（key `quota:pre:{tenant}`，寫入用量後失效）；Redis / DB 不可用時 fail-open 放行。
被擋回應：web / widget `402 {"detail":"quota_exhausted","message":…}`（串流為 `quota_exhausted` 事件）、
LINE 回固定文字、文件狀態 `quota_exhausted`。

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
