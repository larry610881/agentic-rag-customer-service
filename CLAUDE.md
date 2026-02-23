# Agentic RAG Customer Service — 開發規範

## 專案概述

Monorepo 架構的 RAG AI Agent 電商客服平台。採用 DDD（Domain-Driven Design）+ TDD + BDD 開發方法論，後端 Python FastAPI + LangGraph，前端 Next.js App Router。

## Monorepo 結構

```
agentic-rag-customer-service/
├── apps/
│   ├── backend/                # Python FastAPI — DDD 4-Layer
│   │   ├── src/
│   │   │   ├── domain/         # 領域層：Entity, Value Object, Repository Interface
│   │   │   ├── application/    # 應用層：Use Case, Command/Query Handler
│   │   │   ├── infrastructure/ # 基礎設施層：DB, Qdrant, LangGraph, External API
│   │   │   └── interfaces/     # 介面層：FastAPI Router, CLI, Event Handler
│   │   ├── tests/
│   │   └── pyproject.toml
│   └── frontend/               # Next.js 15 App Router
│       ├── src/
│       │   ├── app/            # App Router pages
│       │   ├── components/     # 共用元件
│       │   ├── features/       # 功能模組
│       │   ├── hooks/          # 共用 hooks
│       │   ├── lib/            # 工具函式
│       │   ├── stores/         # Zustand stores
│       │   └── test/           # 測試基礎設施
│       ├── e2e/                # E2E BDD (Playwright)
│       └── package.json
├── packages/                   # 共用套件（未來擴充）
├── infra/                      # Docker / K8s 部署設定
├── data/                       # 種子資料、測試文件
├── Makefile                    # 統一入口指令
└── CLAUDE.md                   # 本檔案
```

## DDD 架構紅線（違反即修正）

1. **Domain 層禁止依賴外層** — `domain/` 不可 import `application/`、`infrastructure/`、`interfaces/`
2. **Application 層禁止直接存取 DB** — Use Case 透過 Repository Interface 操作，不可 import SQLAlchemy / Qdrant client
3. **Infrastructure 層實作 Domain 定義的介面** — Repository Implementation、External Service Adapter 放這裡
4. **Interfaces 層禁止包含業務邏輯** — FastAPI Router 只負責 HTTP 轉換，委派給 Application 層
5. **禁止跨聚合根直接操作** — 聚合之間透過 Domain Event 或 Application Service 協調
6. **禁止 hardcode 機密與環境參數** — 密鑰、連線、timeout 等必須透過 config + `.env` 管理

### 依賴方向圖（只允許向下依賴）

```
Interfaces (interfaces/)
    ↓
Application (application/)
    ↓
Domain (domain/)    ← Infrastructure (infrastructure/) 實作 Domain 介面
```

## 限界上下文（Bounded Contexts）

| 上下文 | 路徑 | 職責 |
|--------|------|------|
| Tenant | `domain/tenant/` | 多租戶管理、租戶隔離 |
| Knowledge | `domain/knowledge/` | 知識庫管理、文件上傳與分塊 |
| RAG | `domain/rag/` | 檢索增強生成、向量搜尋、Prompt 組裝 |
| Conversation | `domain/conversation/` | 對話管理、對話歷史 |
| Agent | `domain/agent/` | LangGraph Agent 編排、Tool 管理 |

## 技術棧

### 後端
| 類別 | 技術 |
|------|------|
| 語言 | Python 3.12+ |
| Web 框架 | FastAPI |
| DI 容器 | dependency-injector |
| AI 編排 | LangGraph |
| 向量資料庫 | Qdrant |
| Embedding | OpenAI / Azure OpenAI |
| LLM | Claude / GPT-4 |
| ORM | SQLAlchemy 2.0 (async) |
| 測試 | pytest + pytest-bdd v8 |

### 前端
| 類別 | 技術 |
|------|------|
| 框架 | Next.js 15 (App Router) |
| UI 元件庫 | shadcn/ui (Tailwind CSS + Radix UI) |
| Client State | Zustand |
| Server State | TanStack Query |
| 表單 | React Hook Form + Zod |
| Unit 測試 | Vitest + React Testing Library |
| Integration 測試 | Vitest + RTL + MSW |
| E2E 測試 | Playwright + playwright-bdd |

## 套件管理

| 範圍 | 工具 | 指令 |
|------|------|------|
| 後端 | uv | `uv sync` / `uv add <pkg>` / `uv run <cmd>` |
| 前端 | npm | `npm install` / `npm run <script>` |
| 統一入口 | make | `make <target>` |

## 常用指令

```bash
# 開發環境
make dev-up                  # 啟動所有服務（Docker Compose）
make dev-down                # 停止所有服務

# 後端
make test-backend            # 後端全量測試
make lint-backend            # 後端 lint (ruff + mypy)
make seed-data               # 種子資料

# 前端
make test-frontend           # 前端全量測試
make lint-frontend           # 前端 lint (ESLint + tsc)
make test-e2e                # E2E BDD 測試

# 全部
make test                    # 後端 + 前端全量測試
make lint                    # 後端 + 前端 lint
```

## 測試策略

### 測試金字塔（60:30:10）

```
        /  E2E  \          Playwright (前端) / pytest-bdd (後端) — 真實服務
       /  Integ  \         MSW (前端) / httpx.AsyncClient (後端) — 真實 DB
      /   Unit    \        Vitest (前端) / pytest (後端) — 完全隔離
```

- 覆蓋率門檻：**80%**
- **後端**：BDD-first（先寫 `.feature`，再寫 step definitions）
- **前端**：TDD + BDD（Unit/Integration 用 TDD，E2E 用 BDD）

### 測試完整性紅線（違反即修正）

1. **全量測試必須通過** — 每次功能完成與 commit 前，執行 `make test`，全部測試（非僅新增的）必須 pass
2. **禁止修改無關測試** — 不得為了消除失敗而修改與本次需求無關的測試（刪除 assert、放寬條件、skip 測試皆屬違規）
3. **失敗歸因原則** — 既有測試失敗 = 你的程式碼有回歸，應修正實作而非修改測試
4. **合法修改測試的唯一條件** — 需求明確要求改變行為，對應測試的斷言必須同步更新
5. **不確定時先報告** — 若既有測試失敗且判斷非本次變更引起，向使用者報告並等待確認

### 後端測試層級對照

| 層級 | 位置 | 工具 | DB | Repository |
|------|------|------|-----|-----------|
| Unit | `tests/unit/` | pytest-bdd + AsyncMock | ❌ Mock | ❌ AsyncMock |
| Integration | `tests/integration/` | pytest-bdd + httpx | ✅ 真實 | ✅ 真實 |
| E2E | `tests/e2e/` | pytest-bdd | ✅ 真實 | ✅ 真實 |

### 前端測試層級對照

| 層級 | 位置 | 工具 | API |
|------|------|------|-----|
| Unit | `*.test.tsx` | Vitest + RTL | vi.mock |
| Integration | `*.integration.test.tsx` | Vitest + RTL + MSW | MSW Handler |
| E2E | `e2e/features/` | playwright-bdd | 真實 API |

## Agent Team 分工

| Agent | Lead | Backend | AI/RAG | Frontend | E2E 整合 |
|-------|:----:|:-------:|:------:|:--------:|:--------:|
| planner | ✓ | | | | ✓ (協調) |
| ddd-checker | ✓ | ✓ | ✓ | | |
| security-reviewer | ✓ | ✓ | | ✓ | |
| test-runner-backend | | ✓ | ✓ | | |
| test-runner-frontend | | | | ✓ | |
| e2e-integration-tester | | | | | ✓ |
| implementation-guide | | ✓ | ✓ | | |
| build-error-resolver | | ✓ | ✓ | ✓ | |
| code-reviewer | | | | ✓ | |
| rag-pipeline-checker | | | ✓ | | |
| ui-designer | | | | ✓ | |

### E2E 整合測試協調規則

涉及前後端的功能，Lead（planner）必須建立 **3 層 Task 結構**：

```
Task: 後端實作  ──┐
                   ├──→ Task: E2E 整合測試 (addBlockedBy: 前兩者)
Task: 前端實作  ──┘      owner: e2e-integration-tester
```

- E2E 通過 → 功能完成
- E2E 失敗 → Lead 分析根因 → 建立修復 Task → 重跑 E2E

## 開發工作流（五階段，不可跳過）

### Stage 1：設計與架構
- 確認限界上下文歸屬
- 規劃 DDD 4 層的檔案落點（Domain → Application → Infrastructure → Interfaces）
- 若涉及 RAG，規劃 LangGraph 節點與 Tool
- 重大決策記錄 ADR

### Stage 2：BDD 行為規格
- **先寫 `.feature` 再寫任何程式碼**
- Gherkin 關鍵字維持英文，描述內容使用繁體中文
- 後端：`apps/backend/tests/features/`
- 前端 E2E：`apps/frontend/e2e/features/`

### Stage 3：TDD 測試
- 根據 `.feature` 撰寫會失敗的測試（紅燈）
- **禁止在沒有對應測試的情況下開始實作功能代碼**
- 後端 Unit Test 必須用 `AsyncMock` mock Repository，禁止真實 DB
- 前端 Unit Test 必須用 `vi.mock()` 隔離依賴

### Stage 4：規範化實作
- **後端** DDD 4-Layer 順序：Domain Entity → Application Use Case → Infrastructure Impl → Interfaces Router
- **前端** 元件開發順序：Type → Hook → Component → Page

### Stage 5：驗證與交付
- 全量測試通過：`make test`
- 無 lint 錯誤：`make lint`
- 覆蓋率 ≥ 80%
- 已 commit 並 push

## Bug Fix 工作流（不可省略測試）

1. **重現**：確認 Bug 的觸發條件與預期行為
2. **寫 Regression Test**：先寫一個會 FAIL 的測試重現 Bug
3. **修復**：修改程式碼直到 regression test 通過
4. **驗證**：全量測試通過 + 覆蓋率不下降

> **原則：每個 Bug fix 都必須留下 regression test。**

## Sprint 管理

- **開發計畫**：`DEVELOPMENT_PLAN.md` — 完整的 S0-S7 Sprint 規劃
- **進度追蹤**：`SPRINT_TODOLIST.md` — 所有 Sprint 任務的 checkbox 追蹤
- **合規檢查**：`/sprint-sync` — 掃描規範合規 + 同步更新 todolist

### Todolist 同步規則

以下情境**必須**同步更新 `SPRINT_TODOLIST.md`：
1. **任務完成時** — 將對應項目標記為 ✅
2. **計畫變更時** — 新增/移除/修改 todolist 項目
3. **開發驗證時** — 執行 `/sprint-sync` 自動掃描並更新
4. **Session 結束前** — Stop hook 會提醒檢查 todolist 是否已同步

## 安全注意事項

- **hardcode 禁止**：密鑰、API key、connection string 必須透過 `.env` 管理
- **.env 管理**：所有 `.env` 檔案已加入 `.gitignore`，禁止提交至版控
- **Prompt Injection 防護**：使用者輸入不得直接拼入 System Prompt，必須透過 RAG Pipeline 的 sanitize 層處理
- **租戶隔離**：所有向量搜尋與知識庫操作必須包含 `tenant_id` 過濾條件
- **前端安全**：禁止 `dangerouslySetInnerHTML`，環境變數使用 `NEXT_PUBLIC_` 前綴
- **CORS**：正式環境禁止 `allow_origins=["*"]`
