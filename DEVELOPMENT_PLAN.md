# RAG AI Agent 電商平台 — 開發計畫總結

## 一、專案概述

建立一個具備 RAG（Retrieval-Augmented Generation）能力的 AI Agent 電商平台，支援多租戶、知識管理、智能問答與 Agentic 工作流。使用 Kaggle 電商資料集建立模擬測試與 Demo 場景。

### 專案範圍

- **多租戶 RAG KM 系統**（四大專案中的專案一）
- **AI Agentic 智慧客服機器人**（結合專案二能力）
- **電商模擬場景**（Kaggle 資料驅動的 Demo）

### 方法論

- **DDD**（Domain-Driven Design）：領域建模、限界上下文、聚合根
- **TDD**（Test-Driven Development）：Red-Green-Refactor 循環
- **BDD**（Behavior-Driven Development）：Gherkin 場景驅動驗收

---

## 二、Repo 策略

### 採用 Monorepo（單一倉庫）

| 比較項目 | Monorepo | Multi-repo |
|---------|----------|------------|
| 跨模組重構 | 一次 PR 搞定 | 多 repo 同步痛苦 |
| 共享型別/Proto | 直接引用 | 需發布 package |
| CI/CD 複雜度 | 中（需 path filter） | 高（多條 pipeline） |
| 新人上手 | clone 一次即可 | 需了解多 repo 關係 |
| 適合團隊規模 | 1-5 人 ✅ | 10+ 人 |

**選擇理由**：個人/小團隊 Side Project，Monorepo 減少切換成本，共享型別方便，前後端協同開發更順暢。

### Repo 名稱

```
agentic-rag-customer-service
```

備選：`rag-agentic-cs-platform`、`multi-tenant-agentic-bot`、`ecommerce-ai-helpdesk`

### Monorepo 目錄結構

```
agentic-rag-customer-service/
├── apps/
│   ├── backend/                 # Python FastAPI
│   │   ├── src/
│   │   │   ├── domain/          # DDD 領域層
│   │   │   │   ├── tenant/      # 租戶領域
│   │   │   │   ├── knowledge/   # 知識管理領域
│   │   │   │   ├── rag/         # RAG 引擎領域
│   │   │   │   └── conversation/# 對話領域
│   │   │   ├── application/     # 應用層（CQRS Commands/Queries）
│   │   │   ├── infrastructure/  # 基礎設施層
│   │   │   └── interfaces/      # API 層
│   │   ├── tests/
│   │   │   ├── bdd/             # BDD 驗收測試
│   │   │   │   ├── features/    # Gherkin .feature 檔
│   │   │   │   └── steps/       # Step 實作
│   │   │   ├── unit/            # TDD 單元測試
│   │   │   └── integration/     # 整合測試
│   │   ├── pyproject.toml
│   │   └── Dockerfile
│   │
│   └── frontend/                # Next.js (React + TypeScript)
│       ├── src/
│       │   ├── app/             # App Router 頁面
│       │   ├── components/      # UI 元件
│       │   ├── features/        # 功能模組
│       │   └── lib/             # 共用工具
│       ├── package.json
│       └── Dockerfile
│
├── packages/                    # 共享套件
│   └── shared-types/            # API 型別定義
│
├── infra/                       # 基礎設施配置
│   ├── docker-compose.yml
│   ├── docker-compose.dev.yml
│   ├── k8s/
│   └── scripts/
│
├── data/                        # Kaggle 測試資料
│   ├── raw/                     # 原始資料
│   ├── processed/               # 處理後資料
│   └── seeds/                   # 種子資料腳本
│
├── docs/                        # 文件
│   ├── architecture/
│   ├── api/
│   └── bdd-scenarios/
│
├── .claude/
│   ├── settings.json            # hooks + agent teams 設定
│   └── hooks/
│       ├── check-task.sh
│       └── check-idle.sh
│
├── CLAUDE.md                    # 專案共享上下文
├── .github/workflows/           # CI/CD
├── README.md
└── Makefile                     # 統一指令入口
```

---

## 三、技術棧

### 前後端語言組合：Python FastAPI + Next.js

| 層級 | 技術選擇 | 理由 |
|------|---------|------|
| 後端 | Python 3.12+ / FastAPI | AI/ML 生態最強，LangGraph/LangChain 原生支援 |
| 前端 | Next.js 14+ / TypeScript | SSR/SSG 彈性、Chat UI 生態豐富、Vercel AI SDK |
| 前後分離 | REST + WebSocket/SSE | API-first 設計，可獨立部署 |

### 詳細技術棧

```yaml
後端:
  語言: Python 3.12+
  框架: FastAPI + Pydantic V2
  AI/Agent:
    - LangGraph (Agentic workflow 編排)
    - LangChain (RAG pipeline)
    - OpenAI / Anthropic SDK (LLM)
  向量資料庫: Qdrant
  關聯式 DB: PostgreSQL
  快取: Redis
  任務佇列: Celery + Redis (或 arq)
  測試: pytest + pytest-bdd + pytest-asyncio
  即時通訊: FastAPI WebSocket / SSE

前端:
  語言: TypeScript
  框架: Next.js 14+ (App Router)
  UI 庫: shadcn/ui + Tailwind CSS
  狀態管理: Zustand / TanStack Query
  即時通訊: Socket.IO client
  圖表: Recharts / Tremor
  測試: Vitest + Playwright

基礎設施:
  容器化: Docker + Docker Compose
  CI/CD: GitHub Actions
  編排: K3s (開發) / K8s (生產)
  監控: Prometheus + Grafana
```

### 方案比較（供參考）

| 組合 | 後端 | 前端 | 優點 | 缺點 |
|------|------|------|------|------|
| **A (採用)** | Python FastAPI | Next.js (React+TS) | AI 生態最強 + 前端生態最強 | Python 高並發相對弱 |
| B | Python FastAPI | Vue 3 + Nuxt 3 | 學習曲線較平緩 | Vue AI/Chat UI 元件庫較少 |
| C | Python + Go 雙後端 | Next.js | Go 處理高並發 | 維護兩套後端複雜度高 |
| D | Node.js (NestJS) | Next.js | 全棧 TS 統一 | AI/ML 生態遠不如 Python |

---

## 四、DDD 領域設計

### 限界上下文

```
┌─────────────┐   ┌───────────────┐   ┌──────────────┐
│ 租戶管理上下文 │──→│ 知識管理上下文  │──→│ RAG 引擎上下文│
│  Tenant      │   │  KnowledgeBase│   │  Query       │
│  Subscription│   │  Document     │   │  Retrieval   │
│  Quota       │   │  Chunk        │   │  Answer      │
└─────────────┘   └───────────────┘   └──────────────┘
                                              │
                                              ▼
                  ┌───────────────┐   ┌──────────────┐
                  │  對話上下文    │←──│ Agent 上下文  │
                  │  Conversation │   │  Tool Router │
                  │  Message      │   │  RAG Tool    │
                  │  Feedback     │   │  Order Tool  │
                  └───────────────┘   │  Ticket Tool │
                                      └──────────────┘
```

### 聚合根設計

| 限界上下文 | 聚合根 | 實體 | 值物件 | 領域事件 |
|-----------|--------|------|--------|---------|
| 租戶管理 | Tenant | Subscription | TenantId, Plan, Quota | TenantCreated, QuotaExceeded |
| 知識管理 | KnowledgeBase | Document, Chunk | DocumentId, ChunkId, Metadata | DocumentUploaded, VectorIndexed |
| RAG 引擎 | Query | Retrieval, Answer | QueryId, Vector, Score | QuerySubmitted, AnswerGenerated |
| 對話 | Conversation | Message | ConversationId, MessageId | ConversationStarted, MessageReceived |

---

## 五、系統架構

```
┌─────────────────────────────────────────────────┐
│                   Frontend (Next.js)             │
│  Chat UI │ Admin Dashboard │ Analytics           │
└──────────────────┬──────────────────────────────┘
                   │ REST + WebSocket/SSE
┌──────────────────▼──────────────────────────────┐
│                 API Gateway (FastAPI)             │
│  Auth Middleware │ Tenant Middleware │ Rate Limit │
└──────────────────┬──────────────────────────────┘
                   │
┌──────────────────▼──────────────────────────────┐
│              Application Layer (CQRS)            │
│  Commands (寫) │ Queries (讀) │ App Services     │
└────────┬────────────────────────┬────────────────┘
         │                        │
┌────────▼────────┐    ┌─────────▼──────────────┐
│  Domain Layer    │    │  AI Agent Layer         │
│  Tenant │ KB     │    │  LangGraph Router       │
│  Document│ Chunk │    │  ├─ RAG Tool            │
│  Conversation    │    │  ├─ Order Tool          │
│  DDD Aggregates  │    │  ├─ Product Tool        │
│                  │    │  ├─ Ticket Tool         │
│                  │    │  └─ Reflection Node     │
└────────┬────────┘    └─────────┬──────────────┘
         │                        │
┌────────▼────────────────────────▼────────────────┐
│              Infrastructure Layer                  │
│  PostgreSQL │ Qdrant │ Redis │ OpenAI/Anthropic   │
│  Celery     │ S3/MinIO                            │
└──────────────────────────────────────────────────┘
```

### AI Agent 路由架構（LangGraph）

```
用戶輸入
    ↓
意圖判斷 (Router Node)
    ├→ 知識查詢 → RAG Tool → 生成回答（帶引用）
    ├→ 訂單查詢 → Order Tool → 格式化回應
    ├→ 商品搜尋 → Product Tool → 推薦展示
    ├→ 投訴處理 → Ticket Tool → 建立工單
    └→ 閒聊     → Direct LLM → 對話回應
         ↓
    Reflection Node（自檢回答品質）
         ↓
    返回用戶
```

---

## 六、Kaggle 資料集計畫

### 資料集選擇

```yaml
主要資料集:
  - Brazilian E-Commerce (Olist):
      URL: kaggle.com/datasets/olistbr/brazilian-ecommerce
      用途: 訂單、商品、客戶、評價 → 模擬電商完整場景
      大小: ~100MB, 10萬+訂單

  - Amazon Product Reviews:
      用途: 商品 FAQ、客戶問題 → RAG 知識庫來源

  - E-Commerce Customer Service Tickets:
      用途: 客服對話 → 訓練意圖識別、測試 Agent 回答品質
```

### 模擬場景

| 場景 | 資料來源 | Agent 工具 |
|------|---------|-----------|
| 商品查詢 | 商品目錄 → 知識庫 | RAG Tool |
| 訂單追蹤 | Olist 訂單表 | Order Tool |
| 退換貨申請 | 退貨政策文件 + 訂單 | RAG Tool + Ticket Tool |
| FAQ | 評價/問答 → 知識庫 | RAG Tool |
| 投訴 | 客服工單資料 | Ticket Tool + Escalation |

---

## 七、Sprint 規劃（共 8 個 Sprint，每 Sprint 2 週）

### 總覽

```
Week  1  2  3  4  5  6  7  8  9  10 11 12 13 14 15 16
      ├──┤  ├──┤  ├──┤  ├──┤  ├──┤  ├──┤  ├──┤  ├──┤
S0    ████                                              基礎建設+資料
S1          ████                                        租戶+知識管理
S2                ████                                  文件處理+向量化
S3                      ████                            RAG 查詢引擎
S4                            ████                      AI Agent+工具
S5                                  ████                前端 MVP
S6                                        ████          Agentic 工作流
S7                                              ████    整合+Demo

後端  ====================================
前端                                ============
AI    ==========================================
測試  ====  ====  ====  ====  ====  ====  ========
```

**總時程：16 週（約 4 個月）**

---

### Sprint 0：基礎建設 + 資料準備（Week 1-2）

**Sprint Goal**：開發環境可一鍵啟動，Kaggle 資料可用

| # | User Story | 任務 | 驗收標準 |
|---|-----------|------|---------|
| 0.1 | 作為開發者，我可以一鍵啟動開發環境 | Docker Compose 建置（PostgreSQL, Redis, Qdrant） | `make dev-up` 啟動所有服務 |
| 0.2 | 作為開發者，我有清晰的專案骨架 | FastAPI DDD 分層 + Next.js App Router 初始化 | 兩端 health check 可通 |
| 0.3 | 作為開發者，我有測試資料可用 | 下載 Kaggle 電商資料集並建立 seed script | `make seed-data` 灌入模擬資料 |
| 0.4 | 作為開發者，CI pipeline 可運行 | GitHub Actions：lint + test + build | PR 自動執行 |

**交付物**：Monorepo 建立 / Docker Compose / Kaggle 資料 ETL / CI pipeline

---

### Sprint 1：租戶核心 + 知識管理領域（Week 3-4）

**Sprint Goal**：多租戶 CRUD 完成，知識庫領域模型建立

| # | User Story | 任務 | 驗收標準 |
|---|-----------|------|---------|
| 1.1 | 作為系統管理員，我可以建立租戶 | Tenant 聚合根 + Repository + API | POST /api/v1/tenants 可建立租戶 |
| 1.2 | 作為租戶管理員，我可以建立知識庫 | KnowledgeBase 聚合根 + 租戶隔離 | 知識庫綁定 tenant_id |
| 1.3 | 作為開發者，認證機制可用 | JWT + 租戶中介軟體 | API 請求自動注入 tenant context |
| 1.4 | 作為 QA，領域模型有測試覆蓋 | TDD 單元測試（配額檢查、租戶隔離） | 覆蓋率 > 80% |

**BDD 場景**：
```gherkin
Scenario: 建立新租戶
  When 我建立租戶 "Acme Shop"，方案為 "Professional"
  Then 應產生唯一 tenant_id
  And 應初始化預設知識庫

Scenario: 租戶資料隔離
  Given 租戶 A 建立了知識庫 "FAQ"
  When 租戶 B 查詢知識庫列表
  Then 不應看到租戶 A 的知識庫
```

---

### Sprint 2：RAG Pipeline - 文件處理 + 向量化（Week 5-6）

**Sprint Goal**：可上傳文件，自動分塊向量化，存入 Qdrant

| # | User Story | 任務 | 驗收標準 |
|---|-----------|------|---------|
| 2.1 | 作為租戶用戶，我可以上傳文件到知識庫 | 文件上傳 API + 格式解析（PDF/TXT/MD） | 上傳後返回 document_id |
| 2.2 | 系統自動將文件分塊 | RecursiveCharacterTextSplitter | 分塊大小 500-1000 tokens |
| 2.3 | 系統自動向量化並存入 Qdrant | Embedding + Qdrant upsert | 向量帶 tenant_id metadata |
| 2.4 | 用 Kaggle 資料建立電商知識庫 | ETL：商品資訊/FAQ/退換貨政策 → 知識庫 | 3 個知識庫，500+ 文件片段 |
| 2.5 | 非同步處理大文件 | Celery 背景任務 + 進度追蹤 | 上傳後返回 task_id，可查詢進度 |

**BDD 場景**：
```gherkin
Scenario: 上傳商品目錄 PDF
  Given 我是租戶 "Acme Shop" 的管理員
  When 我上傳 "product_catalog.pdf" 到知識庫 "Products"
  Then 文件應被分割成多個片段
  And 所有片段應標記為我的 tenant_id
  And Qdrant 應包含對應的向量索引

Scenario: 防止超出配額上傳
  Given 租戶已使用 98GB 配額
  When 我嘗試上傳一個 5GB 的文件
  Then 系統應拒絕上傳並回傳 "配額不足"
```

---

### Sprint 3：RAG 查詢引擎 + 基礎問答（Week 7-8）

**Sprint Goal**：可輸入問題，取得基於知識庫的回答

| # | User Story | 任務 | 驗收標準 |
|---|-----------|------|---------|
| 3.1 | 作為用戶，我可以問問題並得到答案 | 向量檢索 + LLM 生成 | 回答包含 answer + sources |
| 3.2 | 回答附帶來源引用 | Citation 機制 | 每個回答列出來源文件名+片段 |
| 3.3 | 無相關知識時適當處理 | Relevance threshold | 低於閾值回覆「無相關資訊」 |
| 3.4 | 支援 Hybrid Search | BM25 + Vector 混合檢索 | 檢索準確率 > 基準 10% |
| 3.5 | Reranking 提升品質 | Cross-Encoder 重排序 | Top-3 命中率提升 |
| 3.6 | Streaming 回應 | SSE / WebSocket streaming | 前端可逐字顯示 |

**電商驗證場景**：
```
Q: "你們的退貨政策是什麼？" → 基於退換貨政策文件回答，附引用
Q: "商品 X 的規格？"        → 基於商品目錄回答，附引用
Q: "明天天氣如何？"          → "知識庫中沒有相關資訊"
```

---

### Sprint 4：AI Agent 框架 + 電商工具（Week 9-10）

**Sprint Goal**：從純 RAG 進化為 Agentic 架構，Agent 可使用工具

| # | User Story | 任務 | 驗收標準 |
|---|-----------|------|---------|
| 4.1 | 系統能根據意圖選擇不同工具 | LangGraph Agent 框架搭建 | Agent 可路由到不同 tool |
| 4.2 | Agent 可查詢訂單狀態 | OrderLookupTool（查 Kaggle 訂單資料） | 輸入訂單號 → 返回狀態 |
| 4.3 | Agent 可搜尋商品 | ProductSearchTool（查商品目錄） | 輸入關鍵字 → 返回商品列表 |
| 4.4 | Agent 可查詢知識庫 | RAGTool（封裝 Sprint 3 的 RAG） | 問知識型問題走 RAG |
| 4.5 | Agent 可建立工單 | TicketCreationTool | 投訴/退貨 → 自動建立工單 |
| 4.6 | Agent 決策過程可追蹤 | Agent 思考鏈記錄 | 可查看 Agent 選擇工具的理由 |

**BDD 場景**：
```gherkin
Scenario: 訂單查詢自動使用訂單工具
  Given 用戶已登入租戶 "Acme Shop"
  When 用戶問 "我的訂單 ORD-12345 到哪了？"
  Then Agent 應選擇 OrderLookupTool
  And 回答應包含訂單狀態和預計送達時間

Scenario: 複合問題使用多個工具
  When 用戶問 "我想退訂單 ORD-12345 的商品，退貨政策是什麼？"
  Then Agent 應依序使用 OrderLookupTool 和 RAGTool
  And 回答應包含訂單資訊和退貨政策
```

---

### Sprint 5：前端 MVP（Week 11-12）

**Sprint Goal**：Chat UI + 管理後台可用

| # | User Story | 任務 | 驗收標準 |
|---|-----------|------|---------|
| 5.1 | 用戶可以在聊天介面對話 | Chat UI（訊息列表+輸入框+streaming 顯示） | 可發送問題、逐字顯示回答 |
| 5.2 | 回答顯示來源引用 | Citation 元件（可展開查看原文） | 點擊引用可查看來源片段 |
| 5.3 | 管理員可上傳文件 | 文件上傳頁面 + 進度條 | 拖拽上傳，顯示處理進度 |
| 5.4 | 管理員可管理知識庫 | 知識庫 CRUD 頁面 | 新增/編輯/刪除知識庫 |
| 5.5 | 登入 / 租戶切換 | Auth 頁面 + 租戶選擇器 | JWT 登入，切換租戶 |
| 5.6 | Agent 思考過程可視化 | 顯示 Agent 使用了哪些工具 | 用戶可選擇展開「思考過程」 |

**前端頁面規劃**：
```
/                       → Landing Page
/login                  → 登入
/chat                   → Chat UI（主要互動介面）
/admin/knowledge-bases  → 知識庫管理
/admin/documents        → 文件管理
/admin/tenants          → 租戶管理（超級管理員）
/admin/analytics        → 使用統計儀表板
```

---

### Sprint 6：Agentic 工作流 + 多輪對話（Week 13-14）

**Sprint Goal**：Agent 支援複雜工作流、記憶上下文

| # | User Story | 任務 | 驗收標準 |
|---|-----------|------|---------|
| 6.1 | Agent 記住對話上下文 | Conversation Memory（Redis + PostgreSQL） | 追問時理解上文指代 |
| 6.2 | 退貨流程多步驟引導 | LangGraph 子圖：收集資訊 → 驗證 → 建立工單 | 完成 3 步驟退貨申請 |
| 6.3 | 情緒偵測 + 升級人工 | Sentiment Analysis → Escalation | 負面情緒自動提示轉人工 |
| 6.4 | 對話歷史查詢 | 歷史對話 API + 前端列表 | 可查看過去的對話記錄 |
| 6.5 | Agent 自我反思 | Reflection node（自檢回答品質） | 低品質回答自動重新生成 |

**多步驟退貨 Demo Flow**：
```
Agent: 您好，我了解您想退貨。請提供訂單編號。
User:  ORD-12345
Agent: [查詢訂單] 找到了，商品是 XX。請問退貨原因？
        1. 商品瑕疵  2. 不符預期  3. 其他
User:  商品瑕疵
Agent: 了解。已為您建立退貨工單 TK-789。
       我們會在 3 個工作天內安排取件。還有其他問題嗎？
```

---

### Sprint 7：整合測試 + Demo 場景 + 上線準備（Week 15-16）

**Sprint Goal**：系統穩定、Demo 場景完整、可展示

| # | User Story | 任務 | 驗收標準 |
|---|-----------|------|---------|
| 7.1 | 端到端場景通過 | E2E 測試（Playwright） | 5 個核心 user journey 通過 |
| 7.2 | BDD 全場景通過 | pytest-bdd 執行所有 feature | 100% 通過率 |
| 7.3 | 效能可接受 | 壓力測試（Locust） | P95 < 3s，支援 50 並發 |
| 7.4 | Demo 腳本準備 | 5 個 Demo 場景 + 話術 | 每個場景 < 3 分鐘 |
| 7.5 | 文件完整 | README + API doc + 架構圖 | 新人可在 30 分鐘內跑起來 |
| 7.6 | 部署就緒 | Docker Compose 生產配置 | `make prod-up` 一鍵部署 |

### 5 個 Demo 場景

| # | 場景 | 展示重點 |
|---|------|---------|
| 1 | 管理員上傳商品目錄 → 自動建立知識庫 | RAG Pipeline |
| 2 | 客戶詢問商品規格 → AI 基於知識庫回答 | RAG 問答 + 引用 |
| 3 | 客戶查詢訂單狀態 → Agent 自動使用工具 | Agentic Tool Use |
| 4 | 客戶申請退貨 → 多步驟引導 → 建立工單 | 多輪 Agentic 工作流 |
| 5 | 租戶 B 無法看到租戶 A 的資料 | 多租戶隔離 |

---

## 八、Agent Team 配置

### 採用 Claude Code Agent Teams（實驗性功能）

使用 1 Team Lead + 3 Teammates 架構：

| 角色 | 負責範圍 |
|------|---------|
| **Team Lead** | 管理進度、協調任務、審核方案（delegate mode，不寫 code） |
| **Backend** | 資料模型、API、租戶系統、文件儲存 |
| **AI/RAG** | RAG Pipeline、向量化、Agent 框架、LLM 整合 |
| **Frontend** | Chat UI、管理後台（Sprint 5 開始加入） |

### 各 Sprint 分工

| Sprint | Lead | Backend | AI/RAG | Frontend |
|--------|------|---------|--------|----------|
| **0 基礎建設** | 架構設計 | DB + 專案結構 | AI 基礎設施 | - |
| **1 租戶+知識** | 協調 | 租戶 CRUD + Model | 知識管理 Domain | - |
| **2 RAG Pipeline** | 協調 | 文件儲存 API | 文件處理+向量化 | - |
| **3 查詢引擎** | 協調 | Query API | RAG 引擎+問答 | - |
| **4 Agent 框架** | 協調 | 電商工具 API | Agent 框架 | - |
| **5 前端 MVP** | 協調 | API 調整 | - | Chat UI + 後台 |
| **6 Agentic 流程** | 協調 | 對話儲存 | 多輪對話+工作流 | 對話 UI 優化 |
| **7 整合測試** | 驗收 | 後端測試 | AI 測試 | E2E 測試 |

---

## 九、Task 依賴關係

```
Sprint 0:
  Task 1: 建立專案結構 + DB schema（Backend）
  Task 2: 設定 AI 基礎設施 + 向量資料庫（AI/RAG）

Sprint 1:
  Task 3: 租戶 CRUD + Model（Backend）       ← blocked by Task 1
  Task 4: 知識管理 Domain（AI/RAG）           ← blocked by Task 2

Sprint 2:
  Task 5: 文件上傳 API + 儲存層（Backend）    ← blocked by Task 3
  Task 6: 文件解析 + chunking + 向量化（AI/RAG） ← blocked by Task 4

Sprint 3:
  Task 7: Query API（Backend）                ← blocked by Task 5
  Task 8: RAG 引擎 + 基礎問答（AI/RAG）       ← blocked by Task 6

Sprint 4:
  Task 9: 電商工具 API（Backend）              ← blocked by Task 7
  Task 10: Agent 框架 + 工具整合（AI/RAG）     ← blocked by Task 8

Sprint 5:
  Task 11: Chat UI（Frontend）                ← blocked by Task 8
  Task 12: 管理後台（Frontend）               ← blocked by Task 9
  Task 13: API 調整配合前端（Backend）         ← blocked by Task 9

Sprint 6:
  Task 14: 多輪對話 + 工作流（AI/RAG）        ← blocked by Task 10
  Task 15: 對話 UI 優化（Frontend）           ← blocked by Task 11

Sprint 7:
  Task 16: 全端整合測試（全員）               ← blocked by Task 14, 15
  Task 17: Demo 場景建置 + 上線準備（全員）    ← blocked by Task 16
```

---

## 十、MVP 定義（Sprint 0-5 交付）

能 Demo 的最小可用系統：

- [ ] 多租戶註冊 + 登入
- [ ] 文件上傳 → 自動向量化
- [ ] RAG 問答（帶引用）
- [ ] AI Agent 路由（知識查詢 / 訂單查詢 / 建單）
- [ ] Chat UI（streaming 回答）
- [ ] 管理後台（知識庫 + 文件管理）
- [ ] 基於 Kaggle 電商資料的真實場景

MVP 之後（Sprint 6-7）才加入：多輪工作流、情緒偵測、效能優化、完整測試。

---

## 十一、環境設定

### 1. 啟用 Agent Teams

```json
// .claude/settings.json
{
  "env": {
    "CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS": "1"
  }
}
```

### 2. Hooks 設定

```json
// .claude/settings.json
{
  "hooks": {
    "TaskCompleted": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "\"$CLAUDE_PROJECT_DIR\"/.claude/hooks/check-task.sh",
            "timeout": 300
          }
        ]
      }
    ],
    "TeammateIdle": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "\"$CLAUDE_PROJECT_DIR\"/.claude/hooks/check-idle.sh"
          }
        ]
      }
    ],
    "Stop": [
      {
        "hooks": [
          {
            "type": "prompt",
            "prompt": "檢查 $ARGUMENTS 中的對話，確認：1. 所有當前 Sprint 任務都完成 2. 測試都通過 3. 程式碼已 commit。回傳 {\"ok\": true} 或 {\"ok\": false, \"reason\": \"原因\"}",
            "timeout": 30
          }
        ]
      }
    ]
  }
}
```

### 3. Hook 腳本

**check-task.sh**（任務完成前必須通過測試）：
```bash
#!/bin/bash
INPUT=$(cat)
TASK_SUBJECT=$(echo "$INPUT" | jq -r '.task_subject')

if ! uv run python -m pytest tests/ -q --tb=short 2>&1; then
  echo "測試未通過，無法完成任務: $TASK_SUBJECT" >&2
  exit 2
fi

exit 0
```

**check-idle.sh**（隊友閒置前檢查是否有未 commit 的修改）：
```bash
#!/bin/bash
INPUT=$(cat)

if git diff --quiet 2>/dev/null; then
  exit 0
else
  echo "還有未 commit 的修改，請先 commit 再停下" >&2
  exit 2
fi
```

---

## 十二、風險與緩解

| 風險 | 影響 | 緩解策略 |
|------|------|---------|
| LLM API 成本失控 | 高 | 設定 token 預算上限 + 快取常見問答 |
| Agent 幻覺/錯誤路由 | 高 | Reflection 自檢 + Guardrails + 單元測試 |
| 前後端整合延遲 | 中 | Sprint 5 才做前端，API 先行確保穩定 |
| Kaggle 資料不符需求 | 低 | Sprint 0 先驗證資料品質，不行就造 mock |
| 範疇蔓延 | 高 | 嚴守每 Sprint 目標，非核心功能放 backlog |

### Agent Teams 已知限制

- 不支援 session 恢復（resume 不會恢復 teammate）
- 一個 session 只能管一個 team
- Teammate 不能嵌套建立自己的 team
- Split-pane 模式需要 tmux 或 iTerm2（Windows Terminal 不支援）
- Task 狀態偶爾會延遲更新

### Agent Teams vs 子 Agent vs 多終端

| 方式 | 選用時機 |
|------|---------|
| **Agent Teams** | 本專案主要使用，支援 teammate 間直接溝通、共享 Task List |
| **子 Agent（Task tool）** | 單次調查任務，做完即棄 |
| **多終端** | 不建議，彼此無法溝通容易衝突 |

### Token 成本

- 3 個 teammate 約為單一對話的 3-4 倍 token 用量
- 但開發速度可提升 2-3 倍（平行處理）
- 每個 teammate 各自有獨立的 context window

---

## 十三、開發流程

### 執行前準備

```
Phase 1：規劃（先完成）
  → 跟 Claude 逐一討論 Sprint 0-7 的細節
  → 產出完整規劃寫入此文件 + CLAUDE.md

Phase 2：設定環境
  → 啟用 Agent Teams 功能
  → 設定 Hooks（品質管控）
  → 準備 CLAUDE.md（專案共享上下文）

Phase 3：啟動 Agent Team 執行
  → Team Lead 建立所有 Task（含依賴關係）
  → Teammates 按依賴順序自動認領並執行
  → 每 2-3 個 Sprint check-in 檢查品質
```

### 執行流程

```
啟動 Agent Team
    │
    ▼
Sprint 0: Backend + AI/RAG 平行
    │ （Task 1,2 完成 → 自動解鎖 Sprint 1）
    ▼
Sprint 1-4: Backend + AI/RAG 持續平行
    │ （依賴任務完成後自動解鎖下一階段）
    ▼
Sprint 5: Frontend 加入，三線並進
    │
    ▼
Sprint 6: 三線持續
    │
    ▼
Sprint 7: 全員整合測試 + Demo
```

### 品質管控

- **Hooks** 強制每個 Task 完成前通過測試（exit code 2 擋住未通過的）
- **Plan approval** 讓 Lead 審核每個 teammate 的方案再執行
- **Delegate mode** 確保 Lead 只協調不自己寫 code
- 每 2-3 個 Sprint 人工 check-in 檢查方向

---

## 十四、成功指標

### 技術指標

- [ ] 單元測試覆蓋率 > 80%
- [ ] BDD 場景通過率 100%
- [ ] API 回應時間 P95 < 3s
- [ ] 系統可用性 > 99%
- [ ] 支援 50 並發用戶

### 功能指標

- [ ] 支援 100+ 文件，檢索準確率 > 80%
- [ ] Agent 正確路由率 > 90%
- [ ] 5 個 Demo 場景全部可展示
- [ ] 多租戶隔離 0 洩漏

### 學習目標

- [ ] 掌握 DDD/TDD/BDD 完整流程
- [ ] 精通 LangGraph Agentic 架構
- [ ] 深入理解 RAG 技術棧
- [ ] 前後端分離全棧開發經驗
- [ ] 建立完整 Portfolio

---

## 十五、下一步

- [ ] 逐一討論 Sprint 0-7 的詳細需求與技術細節
- [ ] 確定 Kaggle 資料集並驗證資料品質
- [ ] 建立 CLAUDE.md
- [ ] 設定 .claude/settings.json + hooks
- [ ] 建立 GitHub repo：`agentic-rag-customer-service`
- [ ] 啟動 Agent Team 開始執行
