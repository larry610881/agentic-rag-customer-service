# Sprint Todolist — Agentic RAG Customer Service

> 此檔案由 `/sprint-sync` 指令維護。每次計畫變更或開發驗證時同步更新。
>
> 狀態：⬜ 待辦 | 🔄 進行中 | ✅ 完成 | ❌ 阻塞 | ⏭️ 跳過
>
> 最後更新：2026-02-26 (Claude Code 配置最佳實踐修正完成, CLAUDE.md 瘦身 72%)

---

## Sprint 0：基礎建設 + 資料準備（Week 1-2）

**Goal**：開發環境可一鍵啟動，Kaggle 資料可用

### 0.1 開發環境一鍵啟動
- ✅ Docker Compose 建置（PostgreSQL, Redis, Qdrant）
- ✅ `infra/docker-compose.yml` 設定所有服務
- ✅ `infra/docker-compose.dev.yml` 開發覆蓋設定
- ✅ `make dev-up` / `make dev-down` 指令可用
- ✅ 驗收：所有服務 health check 通過

### 0.2 專案骨架建立
- ✅ `apps/backend/pyproject.toml`（FastAPI + pytest-bdd + LangGraph 依賴）
- ✅ `apps/backend/src/` DDD 4-Layer 目錄結構（domain/application/infrastructure/interfaces）
- ✅ `apps/backend/tests/` 測試目錄結構（features/ + unit/ + integration/）
- ✅ `apps/backend/tests/conftest.py` 基礎 fixture
- ✅ 後端 health check endpoint：`GET /api/v1/health` 可通
- ✅ `apps/frontend/` Next.js 15 App Router 初始化
- ✅ `apps/frontend/vitest.config.ts` + `playwright.config.ts` 測試設定
- ✅ `apps/frontend/src/test/setup.ts` + `test-utils.tsx`
- ✅ 前端 health check：`http://localhost:3000` 可通
- ✅ `Makefile` 統一入口指令（dev-up/down, test, lint, seed-data）
- ✅ 驗收：`make test` 可執行（即使 0 測試）

### 0.3 Kaggle 測試資料
- ✅ 下載 Brazilian E-Commerce (Olist) 資料集（`download_kaggle.py` + `make seed-kaggle`）
- ✅ `data/raw/` 存放原始資料
- ✅ ETL 腳本：`data/seeds/` 種子資料產生
- ✅ `make seed-data` 灌入模擬資料
- ✅ ETL 管理 CLI：`manage_data.py`（download/seed/reset/status）
- ✅ 快速匯入：`copy_records_to_table` COPY 協議（~100k rows <15s）
- ✅ 三種模式：auto / mock / kaggle + Demo 訂單 E2E 相容
- ✅ 5 個 Makefile targets：seed-kaggle / seed-mock / seed-reset / seed-reset-all / seed-status
- ✅ 驗收：PostgreSQL 中有訂單/商品/客戶資料

### 0.4 CI Pipeline
- ✅ `.github/workflows/ci.yml`（lint + test + build）
- ✅ PR 自動觸發 CI
- ⬜ 驗收：PR 建立時自動執行 pipeline

---

## Sprint 1：租戶核心 + 知識管理領域（Week 3-4）

**Goal**：多租戶 CRUD 完成，知識庫領域模型建立

### 1.1 租戶 CRUD
- ✅ BDD Feature：`tests/features/unit/tenant/create_tenant.feature`
- ✅ Domain：`Tenant` Entity + `TenantId` VO + `TenantRepository` Interface
- ✅ Application：`CreateTenantUseCase` + `GetTenantUseCase` + `ListTenantsUseCase`
- ✅ Infrastructure：`SQLAlchemyTenantRepository`
- ✅ Interfaces：`POST /api/v1/tenants` + `GET /api/v1/tenants/{id}` + `GET /api/v1/tenants`
- ✅ Unit Test：AsyncMock Repository，覆蓋 happy path + error paths
- ✅ Integration Test：httpx.AsyncClient + 真實 DB（Issue #7, 14 scenarios）
- ✅ 驗收：API 可建立/查詢租戶

### 1.2 知識庫 CRUD
- ✅ BDD Feature：`tests/features/unit/knowledge/create_knowledge_base.feature`
- ✅ Domain：`KnowledgeBase` Entity + `KnowledgeBaseRepository` Interface
- ✅ Application：`CreateKnowledgeBaseUseCase` + `ListKnowledgeBasesUseCase`
- ✅ 知識庫綁定 `tenant_id`（租戶隔離）
- ✅ Unit Test（Integration Test 待 S2）
- ✅ 驗收：API 可建立知識庫，自動綁定 tenant

### 1.3 認證機制
- ✅ JWT Token 發行與驗證（`JWTService`）
- ✅ 租戶中介軟體（從 JWT 取得 tenant_id）
- ✅ `interfaces/api/deps.py` — `get_current_tenant`
- ✅ `POST /api/v1/auth/token` — dev-only token endpoint
- ✅ 驗收：API 請求自動注入 tenant context

### 1.4 測試覆蓋
- ⏭️ 配額檢查 BDD 場景（移至 S2）
- ✅ 租戶隔離 BDD 場景（租戶 B 不可見租戶 A 資料）
- ✅ 驗收：覆蓋率 91.26% > 80%

---

## Sprint 2：RAG Pipeline — 文件處理 + 向量化（Week 5-6）

**Goal**：可上傳文件，自動分塊向量化，存入 Qdrant

### 2.1 文件上傳 API + 多格式解析
- ✅ BDD Feature：`tests/features/unit/knowledge/upload_document.feature`（5 scenarios）
- ✅ BDD Feature：`tests/features/unit/knowledge/file_parsing.feature`（5 scenarios）
- ✅ Domain：`Document` / `Chunk` / `ProcessingTask` Entity + Value Objects
- ✅ Domain：`FileParserService` / `TextSplitterService` ABC（`services.py`）
- ✅ Domain：`DocumentRepository` / `ChunkRepository` / `ProcessingTaskRepository` ABC
- ✅ Application：`UploadDocumentUseCase`
- ✅ Infrastructure：`DefaultFileParserService`（支援 TXT/MD/CSV/JSON/XML/HTML/PDF/DOCX/RTF）
- ✅ Interfaces：`POST /api/v1/knowledge-bases/{kb_id}/documents`（JWT + 10MB 限制）
- ✅ 依賴：pypdf, python-docx, striprtf
- ✅ 驗收：上傳後返回 document_id + task_id

### 2.2 文件分塊
- ✅ BDD Feature：`tests/features/unit/knowledge/document_chunking.feature`（3 scenarios）
- ✅ Infrastructure：`RecursiveTextSplitterService`（langchain-text-splitters）
- ✅ chunk_size=500, chunk_overlap=100
- ✅ Unit Test：短文件 1 chunk、長文件 ≥3 chunks、保留 doc/tenant 關聯
- ✅ 驗收：文件自動分割成多個 chunk

### 2.3 向量化 + Qdrant 存儲
- ✅ BDD Feature：`tests/features/unit/rag/vectorization.feature`（3 scenarios）
- ✅ Domain（RAG）：`EmbeddingService` / `VectorStore` ABC
- ✅ Infrastructure：`FakeEmbeddingService`（hashlib 確定性 1536 維向量）
- ✅ Infrastructure：`OpenAIEmbeddingService`（httpx /v1/embeddings）
- ✅ Infrastructure：`QdrantVectorStore`（AsyncQdrantClient, COSINE distance）
- ✅ Config：`embedding_provider` Selector（fake/openai）
- ✅ 所有向量帶 `tenant_id` metadata，collection 命名 `kb_{kb_id}`
- ✅ 驗收：Qdrant 有對應向量索引

### 2.4 非同步文件處理
- ✅ BDD Feature：`tests/features/unit/knowledge/process_document.feature`（3 scenarios）
- ✅ Application：`ProcessDocumentUseCase`（split → embed → upsert → 更新狀態）
- ✅ Application：`GetProcessingTaskUseCase`
- ✅ Infrastructure：`ChunkModel` / `ProcessingTaskModel` + Repositories
- ✅ Interfaces：`GET /api/v1/tasks/{task_id}`（JWT + tenant 隔離）
- ✅ Document Router 加入 BackgroundTasks 觸發非同步處理
- ✅ 驗收：上傳後返回 task_id，可查詢進度

### 2.5 Kaggle ETL 種子資料
- ✅ `data/seeds/seed_knowledge.py`：18 個 mock 電商文件
- ✅ 3 個知識庫：商品資訊（8 docs）、FAQ（6 docs）、退換貨政策（4 docs）
- ✅ `make seed-knowledge` target
- ✅ 驗收：FakeEmbedding 產生 51 chunks（目標 50-100）

### 2.6 測試與品質
- ✅ 29 BDD scenarios 全部通過（10 S1 + 19 S2）
- ✅ 覆蓋率 83.71% > 80%
- ✅ Lint clean（ruff + mypy）
- ✅ 5 個 git commits 完成

---

## Sprint 3：RAG 查詢引擎 + 基礎問答（Week 7-8）

**Goal**：可輸入問題，取得基於知識庫的回答

### 3.1 基礎 RAG 問答
- ✅ BDD Feature：`tests/features/unit/rag/query_rag.feature`（5 scenarios）
- ✅ Application：`QueryRAGUseCase`（execute + execute_stream）
- ✅ 向量檢索 + LLM 生成回答
- ✅ 回答包含 `answer` + `sources`
- ✅ 驗收：API 可回答知識庫相關問題

### 3.2 來源引用
- ✅ Citation 機制（回答附帶來源文件名 + 片段 + 分數）
- ✅ `Source` Value Object + `RAGResponse` 包含 sources
- ✅ 驗收：每個回答列出來源

### 3.3 無相關知識處理
- ✅ `rag_score_threshold=0.3` + `rag_top_k=5` 設定
- ✅ 低於閾值拋出 `NoRelevantKnowledgeError`
- ✅ BDD 場景：查詢不相關問題
- ✅ API 層攔截 → 200 OK + fallback message

### 3.4 Hybrid Search
- ⏭️ BM25 + Vector 混合檢索（延至 S6）
- ⏭️ 本輪僅 dense vector search + payload filter

### 3.5 Reranking
- ⏭️ Cross-Encoder 重排序（延至 S6）

### 3.6 Streaming 回應
- ✅ SSE streaming：`POST /api/v1/rag/query/stream`
- ✅ `execute_stream()` yield token/sources/done events
- ✅ 驗收：前端可逐字顯示

### 3.7 VectorStore Search + LLM Service
- ✅ BDD Feature：`tests/features/unit/rag/vector_search.feature`（3 scenarios）
- ✅ BDD Feature：`tests/features/unit/rag/llm_service.feature`（3 scenarios）
- ✅ Domain：`SearchResult` / `Source` / `RAGResponse` Value Objects
- ✅ Domain：`VectorStore.search()` + `LLMService` ABC
- ✅ Infrastructure：`FakeLLMService` + `AnthropicLLMService` + `OpenAILLMService`
- ✅ Config：`llm_provider` Selector (fake/anthropic/openai/qwen/openrouter)
- ✅ 驗收：6 scenarios 通過

---

## Sprint 4：AI Agent 框架 + 電商工具（Week 9-10）

**Goal**：從純 RAG 進化為 Agentic 架構

### 4.1 LangGraph Agent 框架
- ✅ BDD Feature：`tests/features/unit/agent/agent_routing.feature`（5 scenarios）
- ✅ BDD Feature：`tests/features/unit/agent/agent_scenarios.feature`（3 scenarios）
- ✅ Domain：`ToolDefinition` / `AgentResponse` / `SupportTicket` Entity
- ✅ Domain：`AgentService` ABC + `OrderLookupService` / `ProductSearchService` / `TicketService` ABC
- ✅ Infrastructure：`FakeAgentService`（關鍵字路由）+ `LangGraphAgentService`（StateGraph）
- ✅ Infrastructure：`build_agent_graph()` — router → tool → respond
- ✅ Interfaces：`POST /api/v1/agent/chat` + `/chat/stream`（SSE）
- ✅ Container：`agent_service` Selector (fake/anthropic/openai)
- ✅ 驗收：Agent 可路由到不同 tool

### 4.2 OrderLookupTool
- ✅ BDD Feature：`tests/features/unit/agent/order_lookup.feature`（3 scenarios）
- ✅ Application：`OrderLookupUseCase`
- ✅ Infrastructure：`SQLOrderLookupService`（Olist 查詢）
- ✅ 驗收：Agent 可查詢訂單

### 4.3 ProductSearchTool
- ✅ BDD Feature：`tests/features/unit/agent/product_search.feature`（2 scenarios）
- ✅ Application：`ProductSearchUseCase`
- ✅ Infrastructure：`SQLProductSearchService`（ILIKE 搜尋）
- ✅ 驗收：Agent 可搜尋商品

### 4.4 RAGTool
- ✅ 封裝 Sprint 3 的 RAG 查詢為 `RAGQueryTool`
- ✅ 驗收：知識型問題走 RAG

### 4.5 TicketCreationTool
- ✅ BDD Feature：`tests/features/unit/agent/ticket_creation.feature`（2 scenarios）
- ✅ Application：`TicketCreationUseCase`
- ✅ Infrastructure：`SQLTicketService` + `TicketModel`（ORM）
- ✅ `support_tickets` table in schema.sql
- ✅ 驗收：Agent 可建立工單

### 4.6 Agent 決策追蹤
- ✅ AgentResponse 包含 `tool_calls` (tool_name + reasoning)
- ✅ BDD 場景：回應包含工具選擇理由
- ✅ 驗收：可查看 Agent 選擇工具的理由

### 4.7 Conversation 領域模型
- ✅ BDD Feature：`tests/features/unit/conversation/conversation_management.feature`（3 scenarios）
- ✅ Domain：`Conversation` / `Message` Entity + `ConversationId` / `MessageId` VO
- ✅ Domain：`ConversationRepository` ABC（S6 實作 DB 持久化）
- ✅ 驗收：對話管理模型就緒

---

## Sprint 5：前端 MVP + LINE Bot（Week 11-12）

**Goal**：Chat UI + 管理後台 + LINE Bot 可用

### 5.1 Chat UI
- ✅ 訊息列表元件（MessageList + MessageBubble）
- ✅ 輸入框 + 送出按鈕（ChatInput + Textarea）
- ✅ Streaming 逐字顯示（useStreaming hook + fetchSSE）
- ✅ Unit Test + Integration Test (MSW)（14 test files, 42 tests）
- ✅ 驗收：可發送問題、看到 AI 回答

### 5.2 Citation 元件
- ✅ 來源引用列表（CitationList + CitationCard, Collapsible）
- ✅ 驗收：點擊引用可查看來源片段

### 5.3 文件上傳頁面
- ✅ 拖拽上傳（UploadDropzone）+ 進度條（UploadProgress + task polling）
- ✅ 驗收：上傳文件並顯示處理進度

### 5.4 知識庫 CRUD 頁面
- ✅ 知識庫列表（KnowledgeBaseList + KnowledgeBaseCard）
- ✅ 新增知識庫（CreateKBDialog + React Hook Form + Zod）
- ✅ 文件管理頁（DocumentList）
- ✅ 文件列表 API + 刪除（含向量清理）— ListDocuments / DeleteDocument Use Case + GET/DELETE 端點 + 前端真實資料 + AlertDialog 確認
- ✅ 驗收：管理員可管理知識庫

### 5.5 登入 + 租戶切換
- ✅ Auth 頁面（LoginForm + JWT 登入 + Zustand auth store）
- ✅ 租戶選擇器（TenantSelector + useTenants hook）
- ✅ AuthGuard（dashboard layout 自動重導）
- ✅ 驗收：可登入並切換租戶

### 5.6 Agent 思考過程可視化
- ✅ 顯示 Agent 使用了哪些工具（ToolCallBadge）
- ✅ 思考過程面板（AgentThoughtPanel, Collapsible）
- ✅ 驗收：用戶可展開「思考過程」

### 5.7 LINE Bot 整合
- ⬜ LINE Developers Console 設定 Messaging API Channel（需手動設定）
- ✅ Domain：`LineTextMessageEvent` Entity + `LineMessagingService` ABC
- ✅ Infrastructure：`HttpxLineMessagingService`（HMAC 簽名驗證 + LINE Reply API）
- ✅ Application：`HandleWebhookUseCase`（Agent → LINE 回覆）
- ✅ Interfaces：`POST /api/v1/webhook/line`（簽名驗證 + BackgroundTasks）
- ✅ 串接 Agent Use Case（與 Web Chat 共用同一套 RAG + Agent Pipeline）
- ✅ Config：line_channel_secret, line_channel_access_token, line_default_tenant_id/kb_id
- ✅ BDD Feature：5 scenarios（文字回覆、簽名驗證、無效簽名、非文字忽略、工具調用）
- ✅ Unit Test：5 step definitions 全部通過
- ✅ 驗收：LINE Bot 可回答知識庫問題 + Agent 工具調用

### 5.8 前端基礎建設
- ✅ shadcn/ui 初始化（15 個 UI 元件）
- ✅ API client（apiFetch wrapper + ApiError）
- ✅ SSE client（fetchSSE + ReadableStream 解析）
- ✅ 共用型別定義（auth, chat, knowledge, api）
- ✅ TanStack Query hooks（auth, tenants, KB, documents, tasks, chat）
- ✅ MSW handlers（7 個 domain handlers）+ test fixtures（3 組）
- ✅ App Router 路由分組：(auth)/login + (dashboard)/chat|knowledge
- ✅ Layout 元件（Sidebar + Header + AppShell）

### 5.9 E2E BDD 測試
- ✅ `e2e/features/auth/login.feature`（3 scenarios）
- ✅ `e2e/features/chat/rag-query.feature`（1 scenario）
- ✅ `e2e/features/chat/agent-chat.feature`（2 scenarios）
- ✅ `e2e/features/knowledge/knowledge-crud.feature`（2 scenarios）
- ✅ `e2e/features/knowledge/upload.feature`（1 scenario）
- ✅ `e2e/features/auth/tenant-isolation.feature`（1 scenario）
- ✅ Page Objects：LoginPage, ChatPage, KnowledgePage, KnowledgeDetailPage, AppLayout
- ✅ Step Definitions：7 個 steps 檔案 + fixtures.ts
- ✅ 驗收：Playwright E2E 10/10 scenarios 全部通過

### 5.10 測試與品質
- ✅ 後端：65 BDD scenarios 通過（60 既有 + 5 LINE Bot 新增）
- ✅ 後端覆蓋率：82.47% > 80%
- ✅ 前端：42 tests 通過（11 unit files + 3 integration files）
- ✅ 前端：tsc --noEmit + ESLint 通過
- ✅ 10 個 git commits 完成（F1-F7 + B1-B3）

---

## Sprint 6：Agentic 工作流 + 多輪對話（Week 13-14）

**Goal**：Agent 支援複雜工作流、記憶上下文

### 6.1 對話持久化 + 記憶
- ✅ ORM：`ConversationModel` + `MessageModel`（PostgreSQL）
- ✅ Infrastructure：`SQLAlchemyConversationRepository`（save, find_by_id, find_by_tenant）
- ✅ Application：`GetConversationUseCase` + `ListConversationsUseCase`
- ✅ `SendMessageUseCase` 注入 ConversationRepository，載入/建立對話，儲存 user+assistant 訊息
- ✅ `conversation_id` 跨請求一致，歷史傳遞給 Agent
- ✅ BDD：3 scenarios（多輪記憶、conversation_id 一致、新對話無歷史）
- ✅ 驗收：多輪對話上下文連貫

### 6.2 對話歷史查詢 API
- ✅ `GET /api/v1/conversations` — 租戶對話列表
- ✅ `GET /api/v1/conversations/{id}` — 對話詳情（含訊息）
- ✅ 租戶隔離驗證
- ✅ BDD：2 scenarios（列表查詢、詳情查詢）
- ✅ 前端對話列表（ConversationList 側欄 + 點選載入歷史對話）
- ✅ 驗收：API 可查看過去的對話記錄

### 6.3 Multi-Agent 架構
- ✅ Domain：`AgentWorker` ABC（`name`, `can_handle()`, `handle()`）+ `WorkerContext` + `WorkerResult`
- ✅ Infrastructure：`SupervisorAgentService`（遍歷 workers 找 can_handle 為 True 的 worker）
- ✅ `FakeMainWorker`（從 FakeAgentService 遷移關鍵字路由）
- ✅ `FakeAgentService` 改為 SupervisorAgentService wrapper
- ✅ Container fake mode 改用 `SupervisorAgentService(workers=[FakeRefundWorker, FakeMainWorker])`
- ✅ 驗收：行為不變，Multi-Agent 架構就緒

### 6.4 退貨多步驟引導
- ✅ Domain：`RefundStep` enum（collect_order, collect_reason, confirm）
- ✅ `FakeRefundWorker`：3 步驟引導（收集訂單號 → 收集原因 → 建立工單）
- ✅ BDD：3 scenarios（收集訂單、收集原因、完成退貨）
- ✅ 驗收：多步驟退貨工作流可用

### 6.5 情緒偵測 + 升級人工
- ✅ Domain：`SentimentService` ABC + `SentimentResult` VO
- ✅ Infrastructure：`KeywordSentimentService`（關鍵字匹配 → negative/positive/neutral）
- ✅ Supervisor 在 dispatch 前分析情緒，負面自動標記 `escalated=True`
- ✅ BDD：2 scenarios（偵測負面升級、正常不升級）
- ✅ 驗收：Escalation 機制可用

### 6.6 Agent 自我反思
- ✅ Supervisor post-processing：回答 < 10 字元自動補充延伸
- ✅ BDD：2 scenarios（反思通過、過短補充）
- ✅ 驗收：回答品質自動把關

### 6.7 測試與品質
- ✅ 84 BDD scenarios 通過（72 既有 + 12 新增）
- ✅ 覆蓋率 84.83% > 80%
- ✅ Ruff clean，mypy 無新增錯誤
- ✅ 7 個 git commits 完成（C1-C7）

---

## Sprint 7 Phase 1：MCP + Multi-Agent 架構基礎（Week 15-16）

**Goal**：2-Tier Supervisor 架構、Domain Events、MCP 基礎就緒

### 7.0 Phase 1 Foundation — Multi-Agent 2-Tier 架構
- ✅ Domain：`WorkerContext` 擴展（user_role, user_permissions, mcp_tools）
- ✅ Domain：`TeamSupervisor` ABC（extends AgentWorker，團隊級 sequential dispatch）
- ✅ ~~Domain：`DomainEvent` 基類 + `EventBus` ABC（shared/events.py）~~ — 已移除（零使用死代碼）
- ✅ ~~Domain：具體事件 — `OrderRefunded`, `NegativeSentimentDetected`, `CampaignCompleted`~~ — 已移除（零使用死代碼）
- ✅ Infrastructure：`MetaSupervisorService`（頂層路由，依 user_role dispatch 到 TeamSupervisor）
- ✅ ~~Infrastructure：`InMemoryEventBus`（記憶體內 Event Bus，開發/測試用）~~ — 已移除（零使用死代碼）
- ✅ Container DI：fake mode 改用 `MetaSupervisorService` + `CustomerTeamSupervisor`
- ✅ BDD Feature：4 個新功能檔（team_supervisor_routing, meta_supervisor_routing, worker_context_expansion, domain_events）
- ✅ BDD Step Definitions：4 個新測試檔，14 scenarios 全部通過
- ✅ 全量測試：98 scenarios 通過（84 既有 + 14 新增）
- ✅ 覆蓋率：85.22% > 80%
- ✅ Lint：ruff clean
- ⏭️ MCPToolWorker 通用 MCP Client Worker — 待 mcp 套件穩定後再實作
- ⏭️ Embedded MCP Server（Knowledge, Conversation, Tenant）— 同上

### 7.0.1 Config 重構 + Qwen/OpenRouter 整合
- ✅ Config：新增 `qwen_api_key`, `openrouter_api_key`, `llm_base_url`, `embedding_base_url`
- ✅ Config：`effective_openai_api_key` property（向下相容 `openai_chat_api_key`）
- ✅ `OpenAILLMService`：constructor 新增 `base_url` 參數
- ✅ Container：`embedding_service` Selector 新增 `qwen` 分支
- ✅ Container：`llm_service` Selector 新增 `qwen`, `openrouter` 分支
- ✅ Container：`agent_service` Selector 新增 `qwen`, `openrouter` 分支
- ✅ `.env.example`：完整 Provider 設定說明
- ✅ BDD Feature：`llm_provider_config.feature`（4 scenarios）
- ✅ 全量測試：102 scenarios 通過，覆蓋率 85.30%

### 7.0.2 Runtime Bug Fixes
- ✅ ORM Models：8 個 model 改用 `DateTime(timezone=True)` 修正 aware/naive timezone mismatch
- ✅ Auth Router：新增 `POST /api/v1/auth/login` 端點（username=tenant name, dev-only）
- ✅ Auth Router：修正 TenantId 序列化（`tenant.id.value` 取代 `str(tenant.id)`）
- ✅ Login Form：登入成功後 `router.replace("/chat")` 導向聊天頁

### 7.0.3 Agent Team E2E 整合協調
- ✅ 新增 `e2e-integration-tester` agent：全棧 E2E 整合測試（API 煙霧 + Playwright + User Journey + 失敗歸因）
- ✅ 更新 `planner` agent：新增 Lead 協調職責（3 層 Task 結構 + E2E 失敗處理循環）
- ✅ 更新 `CLAUDE.md`：Agent Team 表格加入 E2E 整合欄 + 協調規則

### 7.7 UI 強化基礎設施
- ✅ `.mcp.json` 建立（shadcn-ui, context7, magic-ui, playwright）
- ✅ framer-motion 安裝（`apps/frontend/package.json`）
- ✅ `ui-designer` agent 建立（`.claude/agents/ui-designer.md`）
- ✅ `/ui-enhance` skill 建立（`.claude/skills/ui-enhance/SKILL.md`）
- ✅ `ui-design-system` rule 建立（`.claude/rules/ui-design-system.md`）
- ✅ `CLAUDE.md` Agent Team 表格更新
- ⏭️ 驗收：`/ui-enhance KnowledgeBaseCard` 可正常強化 — 待 MCP server 穩定

### 7.8 測試完整性紅線
- ✅ `test-integrity` rule 建立（`.claude/rules/test-integrity.md`）
- ✅ `CLAUDE.md` 測試策略新增「測試完整性紅線」5 條規則

### 7.9 既有測試修復
- ✅ LoginForm unit test：mock `next/navigation` useRouter（`login-form.test.tsx`）
- ✅ LoginForm integration test：mock `next/navigation` useRouter（`login-form.integration.test.tsx`）
- ✅ 全量驗證：Backend 102 passed + Frontend 42 passed

### 7.10 登入流程 Bug 修復
- ✅ Auth store 加入 persist middleware（token 持久化至 localStorage）
- ✅ DashboardLayout 加入 hydration 等待（避免 SSR 時誤導向 login）
- ✅ Root page 改為 client component（已登入→chat，未登入→login）
- ✅ Login page 加入已登入檢查（已有 token 自動導向 chat）
- ✅ Test setup 加入 localStorage.clear()（測試隔離）

### 7.11 E2E BDD 測試套件（Mock Mode）
- ✅ 6 個 feature files（10 scenarios）：auth/knowledge/chat
- ✅ 5 個 Page Objects：LoginPage, ChatPage, KnowledgePage, KnowledgeDetailPage, AppLayout
- ✅ 7 個 step definition files + fixtures.ts
- ✅ bddgen 成功產生 spec files
- ✅ TypeScript 編譯通過
- ✅ API-based login step（繞過 UI，注入 localStorage token + tenantId from JWT）
- ✅ globalSetup 自動 seed 測試資料（KB + tenant）
- ✅ ChatInput 在 KB 未選取前禁用 Send 按鈕（修復競態條件）
- ✅ 後端 DB pool 優化（pool_size=20, pool_pre_ping, pool_recycle=300）
- ✅ playwright.config.ts 加入 screenshot: "on" + video: "on-first-retry" + trace: "on"
- ✅ README.md 新增 E2E 報告模式章節（HTML 報告 + 影片錄製 + Trace Viewer 操作說明）
- ✅ 驗收：Playwright E2E 10/10 scenarios 全部通過 + 43 unit tests green
- ✅ Streaming 端點補發 sources/tool_calls/conversation_id 事件（修復 Demo 2/3/4 阻塞）
- ✅ 多步驟退貨 metadata 傳遞（refund_step 跨對話持久化）
- ✅ Demo 1-4 E2E Feature 檔案 + Step Definitions + POM 增強
- ✅ Playwright config 分 3 project（auth → features → demo）

---

## Sprint 7：整合測試 + Demo + 上線準備（Week 15-16）

**Goal**：系統穩定、Demo 完整、可展示

### 7.1 E2E 全場景測試
- ✅ 10 個 E2E BDD scenarios 全部通過（auth 3 + tenant 1 + chat 3 + knowledge 2 + upload 1）
- ✅ 驗收：Playwright 10/10 通過（docker + backend + frontend + seed data）

### 7.2 BDD 全場景
- ✅ pytest-bdd 執行所有 feature（182 scenarios 全通過）
- ✅ 驗收：100% 通過率

### 7.3 效能測試
- ⏭️ 壓力測試（Locust）— 歸入未來 Sprint，目前聚焦功能開發
- ⏭️ 驗收：P95 < 3s，支援 50 並發

### 7.4 Demo 場景
- ✅ Demo 1：文件上傳與自動向量化（E2E feature + steps）
- ✅ Demo 2：RAG 知識問答與來源引用（E2E feature + streaming 修復）
- ✅ Demo 3：訂單狀態查詢 + OrderLookupTool（E2E feature + tool_calls 事件）
- ✅ Demo 4：退貨多步驟引導（E2E feature + metadata 傳遞修復）
- ✅ Demo 5：租戶隔離驗證（既有 E2E tenant-isolation.feature）
- ✅ Demo 6：LINE Bot 對話 → Agent 回答（5 BDD scenarios mock E2E）
- ✅ 驗收：E2E 14/14 通過 + 後端 107 scenarios 通過

### 7.5 文件
- ✅ README.md 完整（置中 badge、HTML 技術堆疊表、中文化）
- ✅ API 文件：`docs/api-reference.md`
- ✅ 架構圖：`docs/architecture.md`
- ✅ 快速開始：`docs/getting-started.md`
- ✅ Provider 設定指南：`docs/configuration.md`
- ⏭️ ~~Demo 操作手冊：`docs/demo-guide.md`~~（已刪除，Demo 流程整合至 README + getting-started）
- ✅ 驗收：新人可在 30 分鐘內跑起來

### 7.6 部署
- ⏭️ Docker Compose 生產配置 — 歸入未來 Sprint
- ⏭️ `make prod-up` 一鍵部署
- ⏭️ 驗收：生產環境可啟動

### 7.12 機器人管理（Bot Management）
- ✅ Domain：`Bot` Entity + `BotLLMParams` + `BotId` VO + `BotRepository` ABC
- ✅ Infrastructure：`BotModel` + `BotKnowledgeBaseModel`（多對多 join table）+ `SQLAlchemyBotRepository`
- ✅ Application：5 個 Use Cases（Create/List/Get/Update/Delete Bot）
- ✅ Interfaces：`bot_router.py` — CRUD 5 端點（POST/GET/GET/:id/PUT/:id/DELETE/:id）
- ✅ Container + Main 註冊
- ✅ 多 KB RAG 搜尋：`QueryRAGUseCase` 支援 `kb_ids` 跨 KB 搜尋合併排序
- ✅ LLM 參數管線：`LLMService.generate()` 支援 temperature/max_tokens/frequency_penalty kwargs
- ✅ Agent 管線更新：`AgentState` 新增 kb_ids/system_prompt/llm_params，respond_node 支援自訂 System Prompt
- ✅ `SendMessageUseCase` 支援 bot_id → 載入 Bot → 取 kb_ids/system_prompt/llm_params/history_limit
- ✅ `ChatRequest` 新增 bot_id 欄位（backward compatible）
- ✅ LINE Webhook 更新：傳入 kb_ids list
- ✅ BDD：3 feature files + 11 scenarios 全部通過（create_bot 3 + manage_bot 6 + multi_kb_query 2）
- ✅ 前端：types/bot.ts + api-endpoints + query keys + use-bots hooks
- ✅ 前端元件：BotCard + BotList + CreateBotDialog + BotDetailForm（LLM 參數 + KB 綁定 + System Prompt + LINE Channel）
- ✅ 前端頁面：`/bots` 列表頁 + `/bots/[id]` 詳情編輯頁
- ✅ Sidebar 新增 Bots 導航
- ✅ MSW handlers + test fixtures + 4 component test files
- ✅ 全量測試：後端 122 passed + 前端 71 passed
- ✅ 驗收：完整 Bot CRUD + 多 KB 綁定 + LLM 參數 + LINE Channel 設定

### 7.13 Chat 頁面 Bot 選擇流程
- ✅ Chat Store 新增 botId/botName 狀態 + selectBot/clearBot actions
- ✅ ChatRequest 型別新增 bot_id 欄位
- ✅ Streaming hook 改傳 bot_id（後端自動載入 Bot 的 KB/LLM 參數）
- ✅ BotSelector 元件（活躍 Bot 卡片清單 + loading/empty/error 狀態）
- ✅ ConversationList 頂部顯示 Bot 名稱 + 切換按鈕
- ✅ Chat Page 條件渲染：未選 Bot → BotSelector，已選 → 對話介面
- ✅ 測試更新：store 2 + conversation-list 2 = 4 新測試（80 frontend tests green）
- ✅ 驗收：進入 /chat → 選 Bot → 對話 → 可切換 Bot

### 7.14 Embedding / LLM 獨立設定 + 百煉整合
- ✅ Settings 新增 `embedding_api_key` / `llm_api_key` 獨立欄位
- ✅ 新增 `effective_embedding_api_key` / `effective_llm_api_key` 解析 property（dedicated > provider > legacy）
- ✅ Container embedding_service / llm_service 改用統一 key 解析
- ✅ Qwen base URL 統一為 `dashscope.aliyuncs.com`（國內版）
- ✅ `.env.example` 加入百煉 Embedding 模型排序備註 + Quick-Start 範例
- ✅ `.env` 設定 Qwen 全套（embedding=text-embedding-v3 + llm=qwen-plus）
- ✅ 全量測試：後端 127 passed + 前端 80 passed
- ✅ 驗收：Embedding 與 LLM 可獨立設定不同 provider/key

### 7.15 Agent 路由修復 + RAG 隔離測試
- ✅ ChatInput 改用 botId 判斷（修復 knowledgeBaseId 為 null 無法送訊息）
- ✅ Agent tools 可選化：LangGraphAgentService + build_agent_graph 支援 optional tools
- ✅ Qwen provider 暫時只掛 RAG tool（隔離測試用）
- ✅ 寒暄關鍵字路由：你好/嗨/hi/謝謝等直接走 direct，不觸發 RAG
- ✅ respond_node：無 tool_result 時不注入空的工具結果
- ✅ RESPOND_SYSTEM_PROMPT 改善：允許 LLM 在工具結果與問題不相關時自然回答
- ✅ 全量測試：127 backend + 80 frontend passed

### 7.16 Bot 工具選擇 + 真實 SSE Streaming + 工具動畫提示
- ✅ Backend: Bot `enabled_tools` 欄位（domain → application → infrastructure → interfaces 全層）
- ✅ Backend: 動態路由 prompt — `_build_router_prompt()` 只列啟用的工具
- ✅ Backend: 三種路由行為：無工具→直接 LLM / 單工具→跳過路由 / 多工具→LLM 分類
- ✅ Backend: 真實 SSE streaming — `astream(stream_mode="updates")` 逐節點串流
- ✅ Backend: RAG config 注入 — `top_k` / `score_threshold` 從 .env 讀取
- ✅ Backend: `import sqlalchemy` 修復 + ALTER TABLE migration
- ✅ Frontend: `toolHint` Zustand 狀態 + framer-motion 跳動點動畫 (`ToolHintIndicator`)
- ✅ Frontend: Bot enabled_tools 設定 UI（checkboxes in BotDetailForm）
- ✅ Frontend: 測試更新 — bot fixture 加 enabled_tools, BotDetailForm 新增 test
- ✅ 全量測試：127 backend + 81 frontend passed

### 7.17 Per-Bot RAG 參數（top_k / score_threshold）
- ✅ Domain: `BotLLMParams` 新增 `rag_top_k` / `rag_score_threshold` 欄位
- ✅ Infrastructure: DB Model + Repository + lightweight migration
- ✅ Application: Create/Update Bot UseCase 傳遞新欄位
- ✅ Interfaces: API Request/Response 加欄位
- ✅ Agent 呼叫鏈: AgentService → LangGraphAgentService → AgentState → rag_tool_node → RAGQueryTool 全鏈傳遞
- ✅ Frontend: types + BotDetailForm 條件顯示（rag_query 啟用時才出現）+ Zod 驗證
- ✅ 全量測試：127 backend + 81 frontend passed

### 7.18 UI 佈局強化 — Sidebar 收合 + Chat 歷史釘選
- ✅ Zustand store: `useSidebarStore`（isCollapsed + toggle）
- ✅ Sidebar 收合/展開（w-60 ↔ w-14, transition-all duration-200）
- ✅ Nav items 加 lucide icons（MessageSquare / Bot / BookOpen）+ 收合時 Tooltip
- ✅ Toggle button（ChevronsLeft / ChevronsRight）
- ✅ shadcn/ui Tooltip 安裝 + TooltipProvider 注入 Providers
- ✅ AppShell main overflow-auto → overflow-hidden（子頁面自控 scroll）
- ✅ Chat page overflow-hidden + ConversationList h-full 釘選
- ✅ Bots / Knowledge 頁面加 h-full overflow-auto 補丁
- ✅ vitest testTimeout 10s（修復 parallel 環境下 flaky timeout）
- ✅ 全量測試：127 backend + 81 frontend passed

### 7.19 多檔上傳 Bug 修復 + 狀態 Icon 優化
- ✅ Fix 1: `asyncio.to_thread` 包裝同步 file parsing（避免阻塞 event loop）
- ✅ Fix 2: Embedding batching（50 chunks/batch）+ retry（3x 指數退避）+ timeout 120s
- ✅ Fix 3a: 處理失敗時 document 狀態更新為 "failed"
- ✅ Fix 3b: 空 chunks early return（正常完成，不觸發 embedding）
- ✅ Fix 4: 移除 UploadProgress 獨立進度條，改用 DocumentList 表格內狀態呈現
- ✅ Fix 5: DocumentList 狀態欄位改為 lucide-react icon + 中文（等待中/學習中/完成/失敗）
- ✅ Fix 6: UploadDropzone per-file error 追蹤（移除 onUploadStarted prop）
- ✅ Backend regression tests：5 new BDD scenarios（process_document 2 + upload_document 1 + vectorization 2）
- ✅ Frontend regression tests：5 new tests（document-list 4 status icons + upload-dropzone 2 per-file errors）
- ✅ 全量測試：132 backend + 86 frontend passed

### 7.20 對話紀錄 bot_id 隔離
- ✅ Domain: `Conversation` entity 新增 `bot_id: str | None` 欄位
- ✅ Domain: `ConversationRepository.find_by_tenant()` 新增 `bot_id` 篩選參數
- ✅ Application: `ListConversationsUseCase` 支援 `bot_id` 過濾
- ✅ Application: `SendMessageUseCase` 建立新對話時帶入 `bot_id`
- ✅ Infrastructure: ORM Model + composite index + lightweight migration
- ✅ Infrastructure: Repository impl 支援 `bot_id` 持久化 + 查詢過濾
- ✅ Interfaces: API response schemas + `list_conversations` query param
- ✅ Frontend: types + query keys + api-endpoints + useConversations 讀取 botId
- ✅ Frontend: MSW handler 支援 bot_id query param 過濾
- ✅ Application: bot 歸屬驗證 — bot.tenant_id != command.tenant_id 時拋出 DomainException
- ✅ Migration: 啟動時清除 bot_id IS NULL 的對話及其訊息
- ✅ Backend BDD: 5 scenarios（儲存 bot_id / 空 bot_id / 依 bot 過濾 / 無過濾回傳全部 / 跨租戶 bot 驗證）
- ✅ Frontend test: 新增 bot 過濾測試
- ✅ 全量測試：137 backend + 87 frontend passed

### 7.21.1 合成商品資料 + System KB + ProductRecommendTool
- ✅ `data/seeds/schema.sql`：新增 `product_catalog` 表（FK → olist_products）
- ✅ `data/seeds/generate_synthetic_products.py`（NEW）：rule-based 名稱 + template 描述 + 隨機庫存 + AVG 價格
- ✅ `data/seeds/seed_product_knowledge.py`（NEW）：product_catalog → system KB → chunk → embed → Qdrant
- ✅ `data/seeds/seed_postgres.py`：OLIST_TABLES 加入 product_catalog
- ✅ `data/seeds/manage_data.py`：新增 enrich / vectorize 子命令
- ✅ `Makefile`：新增 seed-enrich / seed-vectorize targets
- ✅ Domain：KnowledgeBase 新增 `kb_type` 欄位（"user" | "system"）
- ✅ Domain：KnowledgeBaseRepository 新增 `find_system_kbs()` 方法
- ✅ Infrastructure：ORM Model 新增 `kb_type` + server_default="user"
- ✅ Infrastructure：`find_all_by_tenant` 預設過濾 `kb_type='user'`（系統 KB 前端不可見）
- ✅ Infrastructure：`find_system_kbs()` 回傳 `kb_type='system'` 的 KB
- ✅ Infrastructure：`ProductRecommendTool`（搜尋 system KB 進行商品推薦）
- ✅ Infrastructure：agent_graph 新增 product_recommend 路由 + 工具節點
- ✅ Container：ProductRecommendTool DI 註冊 + 5 個 LangGraphAgentService 注入
- ✅ seed_product_knowledge.py：provider-specific base_url 分流（mirrors container.py）
- ✅ BDD：3 scenarios（成功推薦 / 無 system KB / 無相關商品）
- ✅ 全量測試：140 backend + 87 frontend passed，覆蓋率 80.81%
- ✅ 驗收：3 組連續對話 E2E 驗證（5 個工具全部觸發 + RAG 來源正確引用）

### 7.22 訂單查詢多模式增強（狀態篩選 / 列出全部 / 單筆查詢）
- ✅ Domain：`OrderLookupService.lookup_order()` 擴充為 keyword-only args（order_id / status / limit）
- ✅ Application：新增 `OrderLookupCommand` dataclass + `execute(command)` 簽章
- ✅ Infrastructure：`SQLOrderLookupService` 動態 SQL，支援 3 種查詢模式
- ✅ Infrastructure：`OrderLookupTool.invoke()` 支援多參數
- ✅ Infrastructure：`order_tool_node` 意圖解析（order_id / 狀態中文→英文映射 / list all）
- ✅ Infrastructure：`_ORDER_PATTERN` 新增所有訂單/全部訂單/我的訂單/訂單列表
- ✅ BDD：6 scenarios（3 既有更新 + 3 新增：狀態篩選 / 列全部 / 狀態無結果）
- ✅ 全量測試：143 backend passed
- ✅ Lint：無新增錯誤

### 7.21 Config 外部化（Embedding / Chunking 參數）
- ✅ Config: 新增 `embedding_batch_size`, `embedding_max_retries`, `embedding_timeout`, `embedding_batch_delay`
- ✅ Config: 新增 `chunk_size`, `chunk_overlap`
- ✅ Infrastructure: `OpenAIEmbeddingService` 改為 constructor 注入（移除 module-level 常數）
- ✅ Container: text_splitter_service + embedding_service 3 providers 全部改用 config 注入
- ✅ 全量測試：137 backend + 87 frontend passed

---

## Enterprise Sprint E0：Tool 清理 + Multi-Deploy 架構

**Goal**：移除所有非 RAG 工具及模擬資料，回歸乾淨的 RAG-only SaaS 架構 + 模組化部署

### E0.1 刪除非 RAG 檔案（22 files + 1 directory）
- ✅ Application：刪除 order_lookup / product_search / ticket_creation use cases
- ✅ Infrastructure：刪除 sql_order_lookup / sql_product_search / sql_ticket services + 整個 `tools/` 目錄
- ✅ Domain：刪除 `tool_services.py`（3 個 ABC）
- ✅ DB Model：刪除 `ticket_model.py`
- ✅ Tests：刪除 4 個 feature files + 4 個 step definitions
- ✅ Data Seeds：刪除 5 個 scripts（manage_data / seed_postgres / download_kaggle / generate_synthetic_products / seed_product_knowledge）
- ✅ Frontend E2E：刪除 order-lookup.feature + generated spec

### E0.2 編輯檔案移除非 RAG 引用（20+ files）
- ✅ Domain：移除 `RefundStep` from value_objects；建立 local `_RefundStep` in fake_refund_worker
- ✅ LangGraph：tools.py → RAG-only；agent_graph.py → RAG-only routing；langgraph_agent_service.py → 簡化
- ✅ Container：移除所有非 RAG tool providers；簡化 agent_service wiring
- ✅ DB models/__init__：移除 TicketModel
- ✅ Schema SQL：移除 Olist 表
- ✅ Makefile：移除 7 個 seed 相關 targets
- ✅ Frontend：簡化 tool hints / bot form / test fixtures 為 RAG-only
- ✅ Tests：更新 7 個 BDD features + step definitions

### E0.5 Multi-Deploy 架構
- ✅ `config.py`：新增 `enabled_modules` + `enabled_modules_set` property
- ✅ `main.py`：條件載入 routers（api / websocket / webhook）
- ✅ `infra/deploy-all.env` + `deploy-api.env` + `deploy-bot.env` 部署範本

### E0.6 驗證
- ✅ 全量測試：126 backend passed（移除 17 個非 RAG 測試）
- ✅ Lint：main.py clean，無新增 lint 錯誤
- ✅ 驗收：RAG-only SaaS 架構乾淨就緒

---

## Enterprise Sprint E1：System Provider Settings（DB 化）

**Goal**：將 LLM / Embedding provider 設定從 .env 搬到 DB，Admin 透過 UI 即可管理，免重啟後端

### E1.1 Domain 層：Entity + Repository Interface + EncryptionService ABC
- ✅ `domain/platform/value_objects.py`：ProviderSettingId, ProviderType, ProviderName, ModelConfig
- ✅ `domain/platform/entity.py`：ProviderSetting dataclass（enable/disable）
- ✅ `domain/platform/repository.py`：ProviderSettingRepository ABC
- ✅ `domain/platform/services.py`：EncryptionService ABC
- ✅ BDD：3 scenarios（建立/重複/停用）

### E1.2 Infrastructure 層：AES 加密 + ORM Model + Repository Impl
- ✅ `infrastructure/crypto/aes_encryption_service.py`：AES-256-GCM 加密
- ✅ `infrastructure/db/models/provider_setting_model.py`：SQLAlchemy Model + UniqueConstraint
- ✅ `infrastructure/db/repositories/provider_setting_repository.py`：Repository Impl
- ✅ BDD：2 scenarios（加解密還原/隨機 nonce）

### E1.3 Application 層：CRUD Use Cases + TestConnection
- ✅ 6 個 Use Cases：Create / Update / Delete / List / Get / CheckProviderConnection
- ✅ BDD：5 scenarios（加密/重加密/列出/刪除/測試連線）

### E1.4 Dynamic Factory：DB 優先 → .env 兜底
- ✅ `DynamicLLMServiceFactory` + `DynamicLLMServiceProxy`
- ✅ `DynamicEmbeddingServiceFactory` + `DynamicEmbeddingServiceProxy`
- ✅ Container 整合：Proxy 取代 Selector，下游程式碼零改動
- ✅ BDD：3 scenarios（DB 設定/無設定 fallback/全停用 fallback）

### E1.5 Interfaces 層：REST API Router
- ✅ 6 endpoints：POST/GET/GET/:id/PUT/:id/DELETE/:id + test-connection
- ✅ Response 不含 api_key_encrypted，僅 has_api_key: bool

### E1.6 Frontend：Settings 頁面
- ✅ Types + API endpoints + Query keys + TanStack Query hooks
- ✅ ProviderList 元件（卡片/loading/empty/test connection）
- ✅ ProviderFormDialog 元件（React Hook Form + Zod）
- ✅ Settings pages（/settings → /settings/providers, Tab-based）
- ✅ Sidebar 新增「設定」導航
- ✅ MSW handlers + fixtures + 8 unit tests

### E1 驗證
- ✅ 全量測試：Backend 139 passed + Frontend 8 new tests passed
- ✅ Lint：ruff clean
- ✅ Git commit + push 完成

### E1 後續修復
- ✅ 修復 3 個 E0 清理後未同步的既有測試（message-list ×2 + bot-detail-form）
- ✅ 全量測試：Backend 139 passed + Frontend 95 passed（0 failures）
- ✅ 新增 Issue-Driven 開發流程規則（CLAUDE.md + git-workflow.md）
- ✅ GitHub Issue 補建：#2（E1, closed）+ #1（E1.5, open）
- ✅ gh CLI 安裝（~/bin/gh v2.67.0）

---

## Enterprise Sprint E1.5：LINE Webhook 多租戶

**Goal**：每個 Bot 有獨立 webhook URL `POST /api/v1/webhook/line/{bot_id}`，系統自動從 Bot 取得 LINE 設定、租戶、知識庫

### E1.5.1 Domain + Application：Use Case 重構 + Factory ABC
- ✅ Domain：`LineMessagingServiceFactory` ABC（`services.py`）
- ✅ Application：`HandleWebhookUseCase` 重構 — 新 constructor + `execute_for_bot()` 方法
- ✅ 向後相容：舊 `execute()` 方法透過 `default_line_service` fallback
- ✅ BDD Feature：`line_webhook_multitenant.feature`（5 scenarios）
- ✅ BDD Step Definitions：`test_line_webhook_multitenant_steps.py`
- ✅ 既有測試更新：2 個 step definition 檔案適配新 constructor

### E1.5.2 Infrastructure + Router + Container：Factory Impl + 新端點
- ✅ Infrastructure：`HttpxLineMessagingServiceFactory`（`line_messaging_service_factory.py`）
- ✅ Interfaces：`POST /api/v1/webhook/line/{bot_id}` 新端點 + `_parse_text_events()` 共用抽取
- ✅ Container：`line_messaging_service_factory` Singleton + `handle_webhook_use_case` wiring 更新
- ✅ BDD Feature：`line_webhook_routing.feature`（2 scenarios）
- ✅ BDD Step Definitions：`test_line_webhook_routing_steps.py`

### E1.5 驗證
- ✅ 全量測試：Backend 146 passed + Frontend 95 passed
- ✅ Lint：所有新增/修改檔案 ruff clean
- ✅ Git commit + Issue closed

---

## Enterprise Sprint E2：Feedback System — 回饋收集 + 統計 + Web/LINE 雙通路

**Goal**：在 Web Chat 和 LINE Bot 雙通路加入 thumbs up/down 回饋收集，儲存至 DB，提供基本統計 API

### E2.1 Domain + Application：Feedback Entity / VOs / Repo ABC / Use Cases
- ✅ Domain：`FeedbackId` VO + `Rating` enum + `Channel` enum（feedback_value_objects.py）
- ✅ Domain：`Feedback` Entity（feedback_entity.py）
- ✅ Domain：`FeedbackRepository` ABC（feedback_repository.py）
- ✅ Application：`SubmitFeedbackUseCase`（驗證 conversation + 防重複）
- ✅ Application：`GetFeedbackStatsUseCase`（滿意率計算）
- ✅ Application：`ListFeedbackUseCase`（分頁 + 按對話查詢）
- ✅ BDD：4 scenarios（submit_feedback.feature）+ 2 scenarios（feedback_stats.feature）

### E2.2 Infrastructure + Interfaces：ORM Model / Repo Impl / REST API + Container
- ✅ Infrastructure：`FeedbackModel` ORM（UniqueConstraint on message_id + indexes）
- ✅ Infrastructure：`SQLAlchemyFeedbackRepository`（5 methods）
- ✅ Interfaces：`feedback_router.py` — 4 endpoints（POST / GET list / GET stats / GET by conversation）
- ✅ Container：3 use cases + 1 repository + wiring
- ✅ Main：feedback_router 註冊

### E2.3 Frontend：types / hooks / FeedbackButtons 元件 + tests
- ✅ Types：`feedback.ts`（Rating, Channel, SubmitFeedbackRequest, FeedbackResponse, FeedbackStats）
- ✅ Hooks：`use-feedback.ts`（useSubmitFeedback mutation + useFeedbackStats query）
- ✅ Component：`FeedbackButtons`（ThumbsUp/Down + 展開評論 + tag 選擇 + optimistic update）
- ✅ Integration：`message-bubble.tsx` 加入 FeedbackButtons 渲染
- ✅ Store：`use-chat-store.ts` 加入 `setMessageFeedback` action
- ✅ Types：`chat.ts` 加入 `feedbackRating` 欄位
- ✅ MSW handlers + fixtures + 6 unit tests

### E2.4 LINE Postback：PostbackEvent / Quick Reply / 回饋處理
- ✅ Domain：`LinePostbackEvent` Entity
- ✅ Domain：`LineMessagingService.reply_with_quick_reply()` ABC
- ✅ Infrastructure：`HttpxLineMessagingService.reply_with_quick_reply()` 實作（Quick Reply buttons）
- ✅ Application：`HandleWebhookUseCase.handle_postback()`（解析 feedback:{msg_id}:{rating}）
- ✅ Application：`execute()` / `execute_for_bot()` 改用 reply_with_quick_reply
- ✅ Interfaces：`_parse_postback_events()` + postback 處理
- ✅ Container：`feedback_repository` 注入 handle_webhook_use_case
- ✅ BDD：3 scenarios（line_feedback.feature）

### E2 MVP 驗證
- ✅ 全量測試：Backend 164 passed + Frontend 101 passed
- ✅ Lint：ruff clean
- ✅ Git commit + push + Issue #3 closed

### E2.5 Message Metadata Capture
- ✅ Domain：`Message` 新增 `latency_ms` + `retrieved_chunks` 欄位
- ✅ Domain：`UsageRecord` 新增 `message_id` 欄位
- ✅ Infrastructure：ORM Model 新增欄位 + index
- ✅ Application：`SendMessageUseCase` 計時 + 捕獲 sources（execute + execute_stream）
- ✅ BDD：3 scenarios（message_metadata.feature）

### E2.6 Enhanced LINE Feedback（追問原因）
- ✅ Domain：`LineMessagingService.reply_with_reason_options()` ABC
- ✅ Domain：`FeedbackRepository.update_tags()` ABC
- ✅ Infrastructure：Quick Reply 4 按鈕（feedback_reason postback）+ update_tags impl
- ✅ Application：`handle_postback()` 擴充（thumbs_down → 追問原因 → update_tags）
- ✅ BDD：3 scenarios（line_feedback_reason.feature）

### E2.7 Analysis APIs（4 端點）
- ✅ Domain：`DailyFeedbackStat` / `TagCount` / `RetrievalQualityRecord` VOs
- ✅ Domain：`ModelCostStat` VO + `UsageRepository.get_model_cost_stats()`
- ✅ Application：4 Use Cases（trend / top-issues / retrieval-quality / token-cost）
- ✅ Infrastructure：Repo 實作（GROUP BY, JSON unnest, JOIN messages）
- ✅ Interfaces：4 analysis endpoints + PATCH tags
- ✅ Container：4 use cases 註冊
- ✅ BDD：5 scenarios（feedback_analysis.feature）

### E2.8 Admin Feedback Dashboard（Frontend）
- ✅ 依賴：recharts 安裝 + shadcn/ui table 元件
- ✅ Types：DailyFeedbackStat / TagCount / RetrievalQualityRecord / ModelCostStat
- ✅ API Endpoints：4 analysis + updateTags
- ✅ Query Keys：trend / topIssues / retrievalQuality / tokenCost / list
- ✅ Hooks：6 query hooks + 1 mutation（useSatisfactionTrend / useTopIssues / useRetrievalQuality / useTokenCostStats / useFeedbackList / useFeedbackByConversation / useUpdateFeedbackTags）
- ✅ 元件 ×7：FeedbackStatsSummary / SatisfactionTrendChart / TopIssuesChart / TokenCostTable / FeedbackBrowserTable / ConversationReplay / TagEditor
- ✅ 頁面 ×3：/feedback（總覽）/ /feedback/browser（差評瀏覽器）/ /feedback/[conversationId]（對話回放）
- ✅ Sidebar：新增「回饋分析」nav（BarChart3 icon）
- ✅ MSW Handlers：+5 analysis + PATCH handlers
- ✅ Test Fixtures：+5 analysis mock data
- ✅ 元件測試 ×4（16 tests）：satisfaction-trend-chart / top-issues-chart / feedback-browser-table / tag-editor

### E2.9 Enterprise Data Management
- ✅ Domain：`pii_masking.py`（mask_user_id + mask_pii_in_text）
- ✅ Application：`ExportFeedbackUseCase`（CSV/JSON + PII 遮蔽）
- ✅ Application：`DataRetentionUseCase`（刪除過期回饋）
- ✅ Config：`data_retention_months` + `data_retention_enabled`
- ✅ Interfaces：GET /export + DELETE /retention
- ✅ BDD：7 scenarios（4 export + 3 retention）

### E2 完整版驗證
- ✅ 全量測試：Backend 182 passed + Frontend 117 passed
- ✅ 新增：Backend +18 scenarios（E2.5 ×3 + E2.6 ×3 + E2.7 ×5 + E2.9 ×7）
- ✅ 新增：Frontend +16 tests（E2.8 ×4 test files）

---

## Backlog（已因 E0 清理而關閉）

> 以下 Backlog 項目因 Sprint E0 移除所有非 RAG 工具而不再適用，已關閉。

### ~~B1-B4 — 商品搜尋修復~~（CLOSED — E0 移除）
- ⏭️ product_search / product_recommend 工具已移除，不再需要修復

### ~~D1-D5 — 全 DB 控制 Provider 設定~~（MIGRATED → E1）
- ⏭️ 已遷移至 Enterprise Sprint E1（System Provider Settings DB 化）

---

## ~~Backlog：全 DB 控制 — Embedding / LLM Provider 動態設定~~（COMPLETED via E1）

> ~~**目標**：將目前 `.env` 靜態設定的 Embedding / LLM provider 改為 DB 儲存，支援 UI 動態切換，免重啟後端。~~
>
> **狀態：已由 E1（System Provider Settings DB 化）全部實作完成。**

| D 系列子項 | E1 對應實作 |
|-----------|------------|
| D1 — SystemConfig Domain 模型 | ✅ `ProviderSetting` Entity + `ProviderSettingRepository` ABC |
| D2 — API Key 加密機制 | ✅ AES-256-GCM `EncryptionService` |
| D3 — 動態 Service 重建 | ✅ `DynamicLLMServiceFactory` + `DynamicLLMServiceProxy`（per-tenant） |
| D4 — 管理 UI | ✅ 前端 Settings 頁面（Provider 選擇 + API Key + 連線測試） |
| D5 — Fallback 機制 | ✅ DB → .env fallback chain |

---

## Enterprise Sprint E3：邊緣問題批次修復（Edge Case Batch Fix）

**Goal**：批次修復 E3-E11 已知邊緣問題（E7 Rate Limiting 移至 E4.5）

### E3 — BackgroundTask 錯誤止血
- ✅ `safe_background_task` wrapper（try/except + structlog）
- ✅ `line_webhook_router.py` 4 個 `add_task` 改用 wrapper
- ✅ `document_router.py` 1 個 `add_task` 改用 wrapper
- ✅ BDD：2 scenarios（例外日誌 + 正常無錯誤）

### E5 — LINE Webhook 簽名驗證時序修正
- ✅ event parsing 移入 `execute_for_bot()`，先驗簽再 parse
- ✅ Router 只傳 `body_text` + `signature`，不再預解析 events
- ✅ BDD：2 scenarios（無效簽名先失敗 + malformed event graceful）

### E4 — Bot 查詢 TTL 快取
- ✅ `_bot_cache: dict[str, tuple[Bot, float]]` + `_cache_ttl` 60s
- ✅ `_get_bot_cached()` 方法
- ✅ BDD：2 scenarios（連續查詢只打 1 次 DB + TTL 過期重查）

### E8 — 回饋支援「改變心意」（Upsert）
- ✅ `FeedbackRepository.update()` ABC + 實作
- ✅ `SubmitFeedbackUseCase` 改為 upsert 邏輯
- ✅ BDD：1 修改（重複→更新）+ 1 新增（改變心意附評論）

### E6 — 回饋統計 TTL 快取
- ✅ `GetFeedbackStatsUseCase` 加 `_cache` + `_cache_ttl` 60s
- ✅ BDD：2 scenarios（連續查詢快取 + TTL 過期重查）

### E9 — 分析查詢分頁（跨前後端）
- ✅ Backend：`get_negative_with_context()` 加 `offset`；`count_negative()` 新方法
- ✅ Backend：API 加 `offset` query param + response 含 `total`
- ✅ Frontend：server-side 分頁（`page` state + `offset` 傳遞）
- ✅ BDD：2 scenarios（offset 分頁 + offset 超出範圍）

### E10 — Recharts 動態載入
- ✅ `SatisfactionTrendChart` / `TopIssuesChart` 改 `next/dynamic({ ssr: false })`
- ✅ 既有測試通過即可，無新 BDD

### E11 — PII Regex 擴充
- ✅ +信用卡 `\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}` → `****-****-****-****`
- ✅ +台灣身分證 `[A-Z][12]\d{8}` → `A1***`
- ✅ +IPv4 `\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}` → `***.***.***.***`
- ✅ BDD：3 scenarios（信用卡 + 身分證 + IP 遮蔽）

### E3 驗證
- ✅ 全量測試：Backend 196 passed + Frontend 117 passed
- ✅ 新增：14 BDD scenarios + 1 修改
- ✅ 覆蓋率 >= 80%

---

## Enterprise Sprint E4：EventBus 清理 + 死代碼移除

**Goal**：移除 E3 後盤點發現的零使用死代碼

### E4.1 EventBus 死代碼移除
- ✅ 刪除 `src/domain/shared/events.py`（DomainEvent 基類 + 3 Event + EventBus ABC）
- ✅ 刪除 `src/infrastructure/events/` 整個目錄（InMemoryEventBus + __init__.py）
- ✅ 刪除 `tests/features/unit/agent/domain_events.feature`（4 BDD scenarios）
- ✅ 刪除 `tests/unit/agent/test_domain_events_steps.py`（step definitions）
- ✅ 修改 `src/container.py`（移除 import + event_bus provider）
- ✅ 全量測試：Backend 192 passed（196 - 4 EventBus scenarios）+ Frontend 117 passed（不受影響）

---

## Enterprise Sprint E5：Redis Cache 統一

**Goal**：將所有 in-memory cache 遷移至 Redis，支援多 Worker 部署

### E5.1 CacheService ABC + Redis/InMemory 實作
- ✅ Domain：`CacheService` ABC（`domain/shared/cache_service.py`）— get/set/delete
- ✅ Infrastructure：`RedisCacheService`（graceful degradation on RedisError）
- ✅ Infrastructure：`InMemoryCacheService`（測試用，TTL 支援）
- ✅ Container：`redis_client` + `cache_service` Singleton 注入
- ✅ Main：lifespan shutdown 增加 `redis_client.aclose()`
- ✅ BDD：4 scenarios（set/get, TTL 過期, delete, Redis 斷線 fallback）

### E5.2 Bot 查詢快取 → Redis
- ✅ `HandleWebhookUseCase` 改用 CacheService（移除 dict cache）
- ✅ Bot JSON 序列化/反序列化 helpers（dataclasses.asdict + BotId/datetime 處理）
- ✅ 既有測試更新為 InMemoryCacheService

### E5.3 回饋統計快取 → Redis
- ✅ `GetFeedbackStatsUseCase` 改用 CacheService（移除 dict cache）
- ✅ FeedbackStats JSON 序列化
- ✅ 既有測試更新為 InMemoryCacheService

### E5.4 對話摘要快取 → Redis + TTL
- ✅ `SummaryRecentStrategy` 改用 CacheService（修復記憶體洩漏！）
- ✅ TTL 3600s 防止無限增長
- ✅ BDD：2 scenarios（LLM 只呼叫一次, TTL 設定驗證）

### E5.5 Dynamic LLM Factory 快取 → Redis（加密）
- ✅ `DynamicLLMServiceFactory` 加 cache layer + AES 加密
- ✅ 抽取 `_build_llm_service_from_config()` helper
- ✅ BDD：1 scenario（DB 只查一次）

### E5.6 Dynamic Embedding Factory 快取 → Redis（加密）
- ✅ `DynamicEmbeddingServiceFactory` 同 LLM Factory 模式
- ✅ 抽取 `_build_embedding_service_from_config()` helper
- ✅ BDD：1 scenario（DB 只查一次）

### E5.7 Config TTL + Cache Invalidation
- ✅ Config：4 個 TTL 設定（bot 120s, feedback 60s, summary 3600s, provider 300s）
- ✅ Cache Invalidation：UpdateBotUseCase / DeleteBotUseCase 即時清除 bot 快取
- ✅ Cache Invalidation：UpdateProviderSettingUseCase / DeleteProviderSettingUseCase 即時清除 provider 快取

### E5 驗證
- ✅ 全量測試：Backend 200 passed + Frontend 117 passed
- ✅ 新增：8 BDD scenarios（cache_service 4 + summary_cache 2 + dynamic_factory_cache 2）
- ✅ Lint：ruff clean
- ✅ 3 個 git commits：feat + fix(invalidation) + docs(journal)
- ✅ 架構學習筆記：隱憂已解決/標記 + 延伸學習討論完成

---

## Enterprise Sprint E6：Content-Aware Chunking Strategy

**Goal**：根據檔案 content_type 自動路由到最佳分塊策略，CSV 資料以行為單位切割保持記錄完整性

### E6.1 Domain ABC 擴充
- ✅ `TextSplitterService.split()` 新增 `content_type: str = ""` 可選參數
- ✅ 向後相容：既有呼叫不受影響

### E6.2 CSV Row-Based Splitter
- ✅ 新增 `CSVRowTextSplitterService`（row-based splitting + header 保留）
- ✅ 處理邊界情況：超長行、空 CSV、只有 header
- ✅ metadata 包含 `content_type`, `row_start`, `row_end`

### E6.3 RecursiveTextSplitter 改進
- ✅ 加入中文友善分隔符（。！？；）
- ✅ `split()` 新增 `content_type` 參數 + metadata 擴充

### E6.4 Content-Aware Router（Strategy + Composite Pattern）
- ✅ 新增 `ContentAwareTextSplitterService`
- ✅ 根據 `content_type` 路由到對應策略（text/csv → CSV, 其餘 → Recursive）
- ✅ Open/Closed Principle：新增策略只需註冊，不修改既有代碼

### E6.5 Application Use Case 更新
- ✅ `ProcessDocumentUseCase.split()` 傳入 `content_type=document.content_type`
- ✅ Qdrant payload 擴充 `content_type` + 合併 chunk metadata

### E6.6 Config + Container
- ✅ Config 新增 `chunk_strategy: str = "auto"`（auto / recursive / csv_row）
- ✅ Container Selector：auto → ContentAwareRouter, recursive → Recursive, csv_row → CSV

### E6.7 BDD 測試
- ✅ `csv_chunking.feature`：4 scenarios（行完整性 / header 保留 / 超長行 / 空 CSV）
- ✅ `content_aware_chunking.feature`：3 scenarios（CSV 路由 / default 路由 / fallback）
- ✅ 既有測試零改動，向後相容驗證通過

### E6 驗證
- ✅ 全量測試：Backend 207 passed（200 + 7 新增）+ Frontend 117 passed（不受影響）
- ✅ Lint：所有新增/修改檔案 ruff clean
- ✅ 5 NEW + 5 MODIFY files

---

## 已知邊緣問題（Edge Cases）

> 以下為已識別的邊緣問題。E3-E11（除 E7）已在 E3 Sprint 批次修復。

| # | 問題描述 | 狀態 | 修復方式 |
|---|----------|------|----------|
| E1 | **大檔案 Embedding 429 Rate Limit** | ✅ [#8](https://github.com/larry610881/agentic-rag-customer-service/issues/8) CLOSED | Retry-After header + adaptive batch size |
| ~~E2~~ | ~~product_search 查錯資料表~~ | ~~CLOSED~~ | ~~E0 移除~~ |
| E3 | **BackgroundTask 靜默失敗** | ✅ E3 Sprint | `safe_background_task` wrapper + structlog 錯誤日誌 |
| E4 | **LINE Webhook 無 Bot 查詢快取** | ✅ E5 Redis | CacheService + Redis TTL 120s |
| E5 | **LINE Webhook 簽名驗證時序** | ✅ E3 Sprint | event parsing 移入 Use Case，先驗簽再 parse |
| E6 | **回饋統計即時計算** | ✅ E5 Redis | CacheService + Redis TTL 60s |
| E7 | **回饋 API 無 rate limiting** | ✅ [#9](https://github.com/larry610881/agentic-rag-customer-service/issues/9) CLOSED | User entity + Role + Sliding Window Counter (Redis) + Rate Limit Middleware |
| E8 | **回饋不支援「改變心意」** | ✅ E3 Sprint | 改為 upsert — find existing → update rating/comment/tags |
| E9 | **分析查詢缺少分頁機制** | ✅ E3 Sprint | Backend `offset` + `total_count`；Frontend server-side 分頁 |
| E10 | **Recharts 打包體積** | ✅ E3 Sprint | `next/dynamic` + `{ ssr: false }` 動態載入圖表元件 |
| E11 | **PII 遮蔽不完整** | ✅ E3 Sprint | +信用卡號 +台灣身分證 +IPv4 regex |

---

## Backlog — GitHub Issues 追蹤

> 所有延期項目統一由 GitHub Issues 追蹤，不再散落於各 Sprint 區段。

| Issue | 標題 | Labels | 來源 |
|-------|------|--------|------|
| [#6](https://github.com/larry610881/agentic-rag-customer-service/issues/6) | Content-Aware Chunking Strategy | `rag`, `enhancement` | S3.4, E6 |
| ~~[#7](https://github.com/larry610881/agentic-rag-customer-service/issues/7)~~ | ~~Integration Test 補債~~ | ~~`test`~~ | ~~S1.1, S1.2, S1.4~~ ✅ CLOSED |
| ~~[#8](https://github.com/larry610881/agentic-rag-customer-service/issues/8)~~ | ~~Embedding 429 Rate Limit~~ | ~~`bug`, `rag`~~ | ~~Edge E1~~ ✅ CLOSED |
| ~~[#9](https://github.com/larry610881/agentic-rag-customer-service/issues/9)~~ | ~~API Rate Limiting + 用戶身份~~ | ~~`enhancement`~~ | ~~Edge E7~~ ✅ CLOSED |
| ~~[#15](https://github.com/larry610881/agentic-rag-customer-service/issues/15)~~ | ~~Chunk Quality Monitoring~~ | ~~`enhancement`~~ | ~~E6 延伸~~ ✅ CLOSED |
| [#10](https://github.com/larry610881/agentic-rag-customer-service/issues/10) | MCP 整合 | `enhancement`, `blocked` | S7P1 |
| [#11](https://github.com/larry610881/agentic-rag-customer-service/issues/11) | 生產部署 + 壓力測試 | `infra` | S7.3, S7.6 |
| [#12](https://github.com/larry610881/agentic-rag-customer-service/issues/12) | CI Pipeline 驗收 | `infra` | S0.4 |

---

## 進度總覽

| Sprint | 狀態 | 完成率 | 備註 |
|--------|------|--------|------|
| S0 基礎建設 | ✅ 完成 | 99% | CI 驗收（⬜）為 GitHub 端設定，非程式碼 |
| S1 租戶+知識 | ✅ 完成 | 100% | Unit + Integration Test 完成（Issue #7） |
| S2 文件+向量化 | ✅ 完成 | 100% | 29 scenarios, 83.71% coverage, 51 chunks |
| S3 RAG 查詢 | ✅ 完成 | 100% | 17 scenarios (6+5+6), 82% coverage |
| S4 Agent 框架 | ✅ 完成 | 100% | 非 RAG 工具已在 E0 移除 |
| S5 前端 MVP + LINE Bot | ✅ 完成 | 95% | 65+42 tests, 82% coverage |
| S6 Agentic 工作流 | ✅ 完成 | 100% | 84 scenarios, 84.83% coverage |
| S7P1 Multi-Agent + Config + Agent Team | ✅ 完成 | 100% | 7.0-7.0.3 + 7.7-7.12 完成，MCP 待穩定（⏭️） |
| S7 整合+Demo | ✅ 完成 | 95% | Demo 1-6 ✅、BDD 全通過 ✅、效能/部署歸入未來（⏭️） |
| **E0 Tool 清理 + Multi-Deploy** | **✅ 完成** | **100%** | **22 files 刪除, 20+ files 編輯, 126 backend + 87 frontend tests** |
| **E1 System Provider Settings** | **✅ 完成** | **100%** | **46 files, 2667 insertions, 139 backend + 8 new FE tests** |
| **E1.5 LINE Webhook 多租戶** | **✅ 完成** | **100%** | **11 files, 577 insertions, 146 backend + 95 frontend tests** |
| **E2 Feedback System (MVP)** | **✅ 完成** | **100%** | **39 files, 1604 insertions, 164 backend + 101 frontend tests** |
| **E2 Feedback System (完整版)** | **✅ 完成** | **100%** | **E2.5-E2.9, 182 backend + 117 frontend tests** |
| **E3 Edge Case Batch Fix** | **✅ 完成** | **100%** | **8 fixes (E3-E6,E8-E11), 196 backend + 117 frontend tests** |
| **E4 EventBus 清理** | **✅ 完成** | **100%** | **5 files 刪除 + 1 file 編輯, 192 backend + 117 frontend tests** |
| **E5 Redis Cache 統一** | **✅ 完成** | **100%** | **10 NEW + 10 MODIFY files, 200 backend + 117 frontend tests, 3 commits** |
| **E6 Content-Aware Chunking** | **✅ 完成** | **100%** | **5 NEW + 5 MODIFY files, 207 backend + 117 frontend tests** |
| **Issue #7 Integration Test 補債** | **✅ 完成** | **100%** | **9 NEW + 3 MODIFY, 14 integration scenarios, conftest deadlock fix, coverage omit 修正, 82.90% unit coverage** |
| **Claude Code 配置最佳實踐修正** | **✅ 完成** | **100%** | **CLAUDE.md 358→101 行, ddd-architecture 合併入 python-standards, Learning Review 外移至 rule, settings.local.json 清除 tokens + 精簡權限, -374 行淨刪除** |
| **Issue #15 Chunk Quality Monitoring** | **✅ 完成** | **100%** | **~10 NEW + ~15 MODIFY files, 品質指標+Chunk 預覽+建議+回饋關聯, 239 backend + 130 frontend tests, 82.47% coverage** |
