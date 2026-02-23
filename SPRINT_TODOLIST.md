# Sprint Todolist — Agentic RAG Customer Service

> 此檔案由 `/sprint-sync` 指令維護。每次計畫變更或開發驗證時同步更新。
>
> 狀態：⬜ 待辦 | 🔄 進行中 | ✅ 完成 | ❌ 阻塞 | ⏭️ 跳過
>
> 最後更新：2026-02-23 (Sprint 3+4 完成)

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
- ⬜ 下載 Brazilian E-Commerce (Olist) 資料集
- ✅ `data/raw/` 存放原始資料
- ✅ ETL 腳本：`data/seeds/` 種子資料產生
- ✅ `make seed-data` 灌入模擬資料
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
- ⬜ Integration Test：httpx.AsyncClient + 真實 DB
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
- ✅ Config：`llm_provider` Selector (fake/anthropic/openai)
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

## Sprint 5：前端 MVP（Week 11-12）

**Goal**：Chat UI + 管理後台可用

### 5.1 Chat UI
- ⬜ 訊息列表元件
- ⬜ 輸入框 + 送出按鈕
- ⬜ Streaming 逐字顯示
- ⬜ Unit Test + Integration Test (MSW)
- ⬜ 驗收：可發送問題、看到 AI 回答

### 5.2 Citation 元件
- ⬜ 來源引用列表（可展開查看原文）
- ⬜ 驗收：點擊引用可查看來源片段

### 5.3 文件上傳頁面
- ⬜ 拖拽上傳 + 進度條
- ⬜ 驗收：上傳文件並顯示處理進度

### 5.4 知識庫 CRUD 頁面
- ⬜ 新增/編輯/刪除知識庫
- ⬜ 驗收：管理員可管理知識庫

### 5.5 登入 + 租戶切換
- ⬜ Auth 頁面（JWT 登入）
- ⬜ 租戶選擇器
- ⬜ 驗收：可登入並切換租戶

### 5.6 Agent 思考過程可視化
- ⬜ 顯示 Agent 使用了哪些工具
- ⬜ 驗收：用戶可展開「思考過程」

### 5.7 LINE Bot 整合
- ⬜ LINE Developers Console 設定 Messaging API Channel
- ⬜ Infrastructure：`LineMessagingService`（回覆/推播訊息）
- ⬜ Interfaces：`POST /api/v1/webhook/line`（Webhook 接收 LINE events）
- ⬜ 串接 Agent Use Case（與 Web Chat 共用同一套 RAG + Agent Pipeline）
- ⬜ 支援文字訊息 + 快速回覆按鈕（Quick Reply）
- ⬜ BDD Feature：LINE Webhook 收到訊息 → Agent 回答 → 回傳 LINE
- ⬜ 驗收：LINE Bot 可回答知識庫問題 + Agent 工具調用

### 5.8 E2E BDD 測試
- ⬜ `e2e/features/auth/login.feature`
- ⬜ `e2e/features/conversation/chat.feature`
- ⬜ `e2e/features/knowledge/upload.feature`
- ⬜ 驗收：核心 E2E 場景通過

---

## Sprint 6：Agentic 工作流 + 多輪對話（Week 13-14）

**Goal**：Agent 支援複雜工作流、記憶上下文

### 6.1 對話記憶
- ⬜ Conversation Memory（Redis + PostgreSQL）
- ⬜ BDD 場景：追問時理解上文指代
- ⬜ 驗收：多輪對話上下文連貫

### 6.2 退貨流程多步驟引導
- ⬜ LangGraph 子圖：收集資訊 → 驗證 → 建立工單
- ⬜ BDD 場景：完成 3 步驟退貨申請
- ⬜ 驗收：多步驟退貨工作流可用

### 6.3 情緒偵測 + 升級人工
- ⬜ Sentiment Analysis
- ⬜ 負面情緒自動提示轉人工
- ⬜ 驗收：Escalation 機制可用

### 6.4 對話歷史
- ⬜ 歷史對話 API
- ⬜ 前端對話列表
- ⬜ 驗收：可查看過去的對話記錄

### 6.5 Agent 自我反思
- ⬜ Reflection node（自檢回答品質）
- ⬜ 低品質回答自動重新生成
- ⬜ 驗收：回答品質自動把關

---

## Sprint 7：整合測試 + Demo + 上線準備（Week 15-16）

**Goal**：系統穩定、Demo 完整、可展示

### 7.1 E2E 全場景測試
- ⬜ 5 個核心 user journey E2E 測試
- ⬜ 驗收：Playwright 全部通過

### 7.2 BDD 全場景
- ⬜ pytest-bdd 執行所有 feature
- ⬜ 驗收：100% 通過率

### 7.3 效能測試
- ⬜ 壓力測試（Locust）
- ⬜ 驗收：P95 < 3s，支援 50 並發

### 7.4 Demo 場景
- ⬜ Demo 1：管理員上傳商品目錄 → 自動建立知識庫
- ⬜ Demo 2：客戶詢問商品規格 → AI 基於知識庫回答（帶引用）
- ⬜ Demo 3：客戶查詢訂單狀態 → Agent 使用 OrderLookupTool
- ⬜ Demo 4：客戶申請退貨 → 多步驟引導 → 建立工單
- ⬜ Demo 5：租戶隔離驗證（B 看不到 A 的資料）
- ⬜ Demo 6：LINE Bot 對話 → Agent 回答（同一個 RAG Pipeline）
- ⬜ 驗收：每個場景 < 3 分鐘完成

### 7.5 文件
- ⬜ README.md 完整
- ⬜ API 文件（OpenAPI）
- ⬜ 架構圖
- ⬜ 驗收：新人可在 30 分鐘內跑起來

### 7.6 部署
- ⬜ Docker Compose 生產配置
- ⬜ `make prod-up` 一鍵部署
- ⬜ 驗收：生產環境可啟動

---

## 進度總覽

| Sprint | 狀態 | 完成率 | 備註 |
|--------|------|--------|------|
| S0 基礎建設 | 🔄 進行中 | 95% | 待 Kaggle 下載 + CI 驗收 |
| S1 租戶+知識 | ✅ 完成 | 90% | Unit 完成，Integration Test 待後續 |
| S2 文件+向量化 | ✅ 完成 | 100% | 29 scenarios, 83.71% coverage, 51 chunks |
| S3 RAG 查詢 | ✅ 完成 | 100% | 17 scenarios (6+5+6), 82% coverage |
| S4 Agent 框架 | ✅ 完成 | 100% | 14 scenarios (3+2+3+2+2+5+3), 82% coverage |
| S5 前端 MVP + LINE Bot | ⬜ 待辦 | 0% | S3 完成，可開始；含 LINE Messaging API |
| S6 Agentic 工作流 | ⬜ 待辦 | 0% | S4 完成，可開始 |
| S7 整合+Demo | ⬜ 待辦 | 0% | blocked by S6, 含 LINE Bot Demo |
