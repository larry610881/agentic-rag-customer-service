# Architecture

## DDD 4-Layer

本專案採用 Domain-Driven Design 分層架構，嚴格遵守由外向內的依賴方向。

```
┌─────────────────────────────────────────┐
│           Interfaces 層                  │
│   FastAPI Router, CLI, Event Handler     │
│   只負責 HTTP/CLI 轉換，委派給 App 層    │
└──────────────────┬──────────────────────┘
                   ↓
┌─────────────────────────────────────────┐
│          Application 層                  │
│   Use Case, Command/Query Handler        │
│   編排 Domain 物件，呼叫 Repository      │
└──────────────────┬──────────────────────┘
                   ↓
┌─────────────────────────────────────────┐
│            Domain 層                     │
│   Entity, Value Object, Domain Event     │
│   Repository Interface, Domain Service   │
│   ★ 核心：不依賴任何外層 ★               │
└─────────────────────────────────────────┘
                   ↑ 實作
┌─────────────────────────────────────────┐
│        Infrastructure 層                 │
│   Repository Impl, DB, Qdrant, LangGraph │
│   External API Adapter, Cache            │
└─────────────────────────────────────────┘
```

### 依賴規則

| 層級 | 可依賴 | 禁止依賴 |
|------|--------|----------|
| Domain | Python 標準庫, pydantic | Application, Infrastructure, Interfaces |
| Application | Domain | Infrastructure 具體實作, Interfaces |
| Infrastructure | Domain (Interface) | Application, Interfaces |
| Interfaces | Application, Domain DTO | Infrastructure 直接操作 |

### Bounded Contexts（限界上下文）

| 上下文 | 路徑 | 職責 |
|--------|------|------|
| Tenant | `domain/tenant/` | 多租戶管理、租戶隔離 |
| Knowledge | `domain/knowledge/` | 知識庫管理、文件上傳與分塊 |
| RAG | `domain/rag/` | 檢索增強生成、向量搜尋、Prompt 組裝 |
| Conversation | `domain/conversation/` | 對話管理、歷史記錄 |
| Agent | `domain/agent/` | LangGraph Agent 編排、Tool 管理 |

## Multi-Agent 2-Tier 架構

```
                    使用者訊息
                        │
                        ▼
              ┌─────────────────┐
              │ MetaSupervisor  │   路由 + 情緒偵測
              │   (Tier 1)      │
              └────────┬────────┘
                       │
          ┌────────────┼────────────┐
          ▼            ▼            ▼
   ┌────────────┐ ┌────────────┐ ┌────────────┐
   │ Customer   │ │ Sales      │ │ Technical  │
   │ Team       │ │ Team       │ │ Team       │
   │ Supervisor │ │ Supervisor │ │ Supervisor │
   │ (Tier 2)   │ │ (Tier 2)   │ │ (Tier 2)   │
   └──────┬─────┘ └────────────┘ └────────────┘
          │
     ┌────┼────┐
     ▼         ▼
┌─────────┐ ┌─────────┐
│ Refund  │ │ Main    │
│ Worker  │ │ Worker  │
└─────────┘ └─────────┘
```

**Tier 1 — MetaSupervisor**：接收使用者訊息，進行情緒偵測與路由，分派至對應 Team。

**Tier 2 — TeamSupervisor**：管理 Team 內的 Worker，根據意圖選擇合適的 Worker 處理。

**Workers**：執行具體任務（退貨處理、一般問答、訂單查詢等）。

### Domain Events

跨聚合通訊透過 Domain Event 進行：

```
Agent 回應完成
    → AgentResponseCompleted Event
        → 記錄對話歷史
        → 記錄 Usage 用量
        → 觸發情緒反思（必要時）
```

## RAG Pipeline

```
┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐
│ Upload   │───▶│ Parse &  │───▶│ Embed    │───▶│ Store in │
│ Document │    │ Chunk    │    │ Vectors  │    │ Qdrant   │
└──────────┘    └──────────┘    └──────────┘    └──────────┘

┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐
│ User     │───▶│ Embed    │───▶│ Vector   │───▶│ LLM      │
│ Query    │    │ Query    │    │ Search   │    │ Generate │
└──────────┘    └──────────┘    └──────────┘    └──────────┘
```

### Ingestion Flow

1. **Upload** — 使用者上傳文件（PDF, TXT, MD）
2. **Parse** — `FileParserService` 解析文件內容
3. **Chunk** — `TextSplitterService` 將文本分塊（500 chars, 100 overlap）
4. **Embed** — `EmbeddingService` 將每個 chunk 向量化
5. **Store** — `VectorStore` 存入 Qdrant（含 tenant_id payload）

### Query Flow

1. **Query** — 使用者提問
2. **Embed** — 將問題向量化
3. **Search** — Qdrant 向量相似搜尋（top-k + score threshold + tenant 隔離）
4. **Augment** — 將檢索結果注入 Prompt context
5. **Generate** — LLM 根據 context 生成回答

## 技術棧

### 後端

| 類別 | 技術 |
|------|------|
| 語言 | Python 3.12+ |
| Web 框架 | FastAPI |
| DI 容器 | dependency-injector |
| AI 編排 | LangGraph |
| 向量資料庫 | Qdrant |
| ORM | SQLAlchemy 2.0 (async) |
| 測試 | pytest + pytest-bdd v8 |

### 前端

| 類別 | 技術 |
|------|------|
| 框架 | Next.js 15 (App Router) |
| UI | shadcn/ui (Tailwind CSS + Radix UI) |
| Client State | Zustand |
| Server State | TanStack Query |
| 測試 | Vitest + RTL + Playwright |
