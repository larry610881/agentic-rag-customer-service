<div align="center">

# Agentic RAG Customer Service

<p><strong>AI 驅動的 RAG 多租戶電商客服平台 — 結合檢索增強生成、多代理編排與完整計費治理</strong></p>

[![Python](https://img.shields.io/badge/Python-3.12+-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-009688?style=for-the-badge&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![React](https://img.shields.io/badge/React_19-61DAFB?style=for-the-badge&logo=react&logoColor=black)](https://react.dev/)
[![Vite](https://img.shields.io/badge/Vite-646CFF?style=for-the-badge&logo=vite&logoColor=white)](https://vitejs.dev/)
[![TypeScript](https://img.shields.io/badge/TypeScript-3178C6?style=for-the-badge&logo=typescript&logoColor=white)](https://www.typescriptlang.org/)
[![LangGraph](https://img.shields.io/badge/LangGraph-1C3C3C?style=for-the-badge&logo=langchain&logoColor=white)](https://langchain-ai.github.io/langgraph/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-4169E1?style=for-the-badge&logo=postgresql&logoColor=white)](https://www.postgresql.org/)
[![Milvus](https://img.shields.io/badge/Milvus-00A1EA?style=for-the-badge&logo=milvus&logoColor=white)](https://milvus.io/)

</div>

---

## 目錄

- [功能特色](#-功能特色)
- [系統架構](#-系統架構)
- [技術堆疊](#-技術堆疊)
- [環境需求](#-環境需求)
- [快速開始](#-快速開始)
- [指令一覽](#-指令一覽)
- [專案結構](#-專案結構)
- [測試策略](#-測試策略)
  - [E2E 測試執行與影片錄製](#e2e-測試執行與影片錄製)
- [文件](#-文件)
- [授權](#-授權)

---

## ✨ 功能特色

### 🎯 核心能力

| 功能 | 說明 |
|------|------|
| **多租戶架構** | 租戶級資料隔離，每個租戶獨立的知識庫、機器人、方案配額 |
| **RAG Pipeline** | Contextual Retrieval 上下文切片 + LLM 自動分類 + 引用來源 |
| **多代理編排（Sub-agent）** | Meta Supervisor 分派 Worker（政策/商品/訂單等），處理複合型問題 |
| **ReAct Agent** | LangGraph 驅動的 ReAct 推理，Tool Calling + MCP 生態整合 |
| **串流對話** | SSE 即時串流、對話歷史側欄、cache token 計費感知 |
| **多通路接入** | Web 前台、Web 後台、LINE Webhook、Widget 嵌入式 |
| **機器人工作室（Studio）** | 即時檢視 AI 每一步路線：路由決策 → 工具 → 知識庫 → 生成 |

### 📊 平台治理（Token-Gov）

| 功能 | 說明 |
|------|------|
| **Token 額度管理** | 雙層 Ledger（base + addon），每月自動重置、cycle 切換 |
| **自動續約 + 門檻警示** | addon 耗盡自動補充，額度低於門檻觸發 SendGrid email |
| **收益儀表板** | 跨租戶收入、cost 分析、每月趨勢 |
| **額度事件稽核** | quota_events 完整留痕（add/deduct/topup/monthly_reset）|
| **Guard / Rate Limit** | Prompt Injection 防禦、租戶級 API 速率限制 |

### 🔬 可觀測性

| 功能 | 說明 |
|------|------|
| **Agent Trace** | 每次對話完整 DAG（節點/時序/token/cost），支援 filter + 聚合 |
| **Feedback System** | 使用者回饋收集 + 滿意度趨勢 + Top Issues 分析 |
| **Error Events** | 跨前後端錯誤統一收納與狀態追蹤 |
| **日誌清理** | 自動保留 policy + 批次清理 |

---

## 🏗 系統架構

<div align="center">
  <a href="docs/images/architecture_diagrams.png">
    <img src="docs/images/architecture_diagrams.png" alt="System Architecture" width="800" />
  </a>
  <p><sub>點擊圖片可放大檢視</sub></p>
</div>

> **DDD 4-Layer**：Domain → Application → Infrastructure → Interfaces
> **5 個限界上下文**：Tenant / Knowledge / RAG / Conversation / Agent
> **背景任務**：arq + Redis（process_document / split_pdf / classify_kb / extract_memory / run_evaluation）

---

## 📦 技術堆疊

<table>
  <tr>
    <th align="left">Frontend</th>
    <td>
      <img src="https://img.shields.io/badge/React_19-61DAFB?logo=react&logoColor=black" alt="React 19" />
      <img src="https://img.shields.io/badge/Vite-646CFF?logo=vite&logoColor=white" alt="Vite" />
      <img src="https://img.shields.io/badge/TypeScript-3178C6?logo=typescript&logoColor=white" alt="TypeScript" />
      <img src="https://img.shields.io/badge/React_Router_v6-CA4245?logo=reactrouter&logoColor=white" alt="React Router" />
      <img src="https://img.shields.io/badge/Tailwind_CSS_4-06B6D4?logo=tailwindcss&logoColor=white" alt="Tailwind" />
      <img src="https://img.shields.io/badge/shadcn/ui-000?logo=shadcnui&logoColor=white" alt="shadcn/ui" />
      <img src="https://img.shields.io/badge/Zustand-443E38?logo=react&logoColor=white" alt="Zustand" />
      <img src="https://img.shields.io/badge/TanStack_Query-FF4154?logo=reactquery&logoColor=white" alt="TanStack Query" />
      <img src="https://img.shields.io/badge/framer--motion-0055FF?logo=framer&logoColor=white" alt="framer-motion" />
      <img src="https://img.shields.io/badge/recharts-22B5BF?logo=react&logoColor=white" alt="Recharts" />
    </td>
  </tr>
  <tr>
    <th align="left">Backend</th>
    <td>
      <img src="https://img.shields.io/badge/Python_3.12+-3776AB?logo=python&logoColor=white" alt="Python" />
      <img src="https://img.shields.io/badge/FastAPI-009688?logo=fastapi&logoColor=white" alt="FastAPI" />
      <img src="https://img.shields.io/badge/SQLAlchemy_2.0-D71F00?logo=sqlalchemy&logoColor=white" alt="SQLAlchemy" />
      <img src="https://img.shields.io/badge/Pydantic_v2-E92063?logo=pydantic&logoColor=white" alt="Pydantic" />
      <img src="https://img.shields.io/badge/dependency--injector-4B8BBE?logo=python&logoColor=white" alt="DI" />
      <img src="https://img.shields.io/badge/arq-DC382D?logo=redis&logoColor=white" alt="arq" />
      <img src="https://img.shields.io/badge/uv-DE5FE9?logo=python&logoColor=white" alt="uv" />
    </td>
  </tr>
  <tr>
    <th align="left">AI / RAG</th>
    <td>
      <img src="https://img.shields.io/badge/LangGraph-1C3C3C?logo=langchain&logoColor=white" alt="LangGraph" />
      <img src="https://img.shields.io/badge/Milvus-00A1EA?logo=milvus&logoColor=white" alt="Milvus" />
      <img src="https://img.shields.io/badge/OpenAI-412991?logo=openai&logoColor=white" alt="OpenAI" />
      <img src="https://img.shields.io/badge/Anthropic-191919?logo=anthropic&logoColor=white" alt="Anthropic" />
      <img src="https://img.shields.io/badge/Ollama-000?logo=ollama&logoColor=white" alt="Ollama" />
      <img src="https://img.shields.io/badge/MCP-000?logo=anthropic&logoColor=white" alt="Model Context Protocol" />
    </td>
  </tr>
  <tr>
    <th align="left">Database / Storage</th>
    <td>
      <img src="https://img.shields.io/badge/PostgreSQL-4169E1?logo=postgresql&logoColor=white" alt="PostgreSQL" />
      <img src="https://img.shields.io/badge/Redis-DC382D?logo=redis&logoColor=white" alt="Redis" />
      <img src="https://img.shields.io/badge/Milvus-00A1EA?logo=milvus&logoColor=white" alt="Milvus" />
    </td>
  </tr>
  <tr>
    <th align="left">Testing</th>
    <td>
      <img src="https://img.shields.io/badge/pytest-0A9EDC?logo=pytest&logoColor=white" alt="pytest" />
      <img src="https://img.shields.io/badge/pytest--bdd-0A9EDC?logo=pytest&logoColor=white" alt="pytest-bdd" />
      <img src="https://img.shields.io/badge/Vitest-6E9F18?logo=vitest&logoColor=white" alt="Vitest" />
      <img src="https://img.shields.io/badge/Playwright-2EAD33?logo=playwright&logoColor=white" alt="Playwright" />
      <img src="https://img.shields.io/badge/MSW-FF6A33?logo=mockserviceworker&logoColor=white" alt="MSW" />
    </td>
  </tr>
  <tr>
    <th align="left">DevOps / Cloud</th>
    <td>
      <img src="https://img.shields.io/badge/Docker-2496ED?logo=docker&logoColor=white" alt="Docker" />
      <img src="https://img.shields.io/badge/Cloud_Run-4285F4?logo=googlecloud&logoColor=white" alt="Cloud Run" />
      <img src="https://img.shields.io/badge/GitHub_Actions-2088FF?logo=githubactions&logoColor=white" alt="GitHub Actions" />
      <img src="https://img.shields.io/badge/SendGrid-1A82E2?logo=minutemailer&logoColor=white" alt="SendGrid" />
      <img src="https://img.shields.io/badge/Make-427819?logo=gnu&logoColor=white" alt="Make" />
    </td>
  </tr>
</table>

---

## 📋 環境需求

| 工具 | 版本 | 用途 |
|------|------|------|
| Docker & Docker Compose | latest | PostgreSQL、Milvus、Redis 容器 |
| Python | 3.12+ | 後端執行環境 |
| uv | latest | Python 套件管理（禁止 pip install） |
| Node.js | 20+ | 前端執行環境 |
| Make | any | 統一指令入口 |

> **注意**：本專案使用 Docker Engine（非 Docker Desktop），指令一律 `docker` / `docker compose`，禁止 `podman`。

---

## 🚀 快速開始

```bash
# 1. Clone 專案
git clone https://github.com/larry610881/agentic-rag-customer-service.git
cd agentic-rag-customer-service

# 2. 啟動基礎設施 (PostgreSQL, Milvus, Redis)
make dev-up

# 3. 設定環境變數
cp apps/backend/.env.example apps/backend/.env
cp apps/frontend/.env.example apps/frontend/.env.local
# 編輯 .env 填入 API Key (OpenAI / Anthropic 等)

# 4. 安裝依賴
make install

# 5. 啟動開發伺服器
cd apps/backend && uv run uvicorn src.main:app --reload --port 8001 &
cd apps/frontend && npm run dev &
```

| 服務 | 網址 |
|------|------|
| Frontend (Vite SPA) | http://localhost:5174 |
| Backend API Docs | http://localhost:8001/docs |
| Milvus gRPC | `localhost:19530`（Python SDK 連線 port） |
| Milvus Health | http://localhost:9091/healthz |

> **Port 分配**：見 `~/.config/dev-ports/registry.json`（agentic-rag backend=8001、frontend=5174）

---

## 🛠 指令一覽

| 指令 | 說明 |
|------|------|
| `make dev-up` | 啟動 Docker Compose 服務 |
| `make dev-down` | 停止 Docker Compose 服務 |
| `make install` | 安裝後端 + 前端依賴 |
| `make test` | 執行全部測試（後端 + 前端） |
| `make test-backend` | 執行後端 pytest 測試 |
| `make test-frontend` | 執行前端 Vitest 測試 |
| `make lint` | 全量 Lint（ruff + mypy + ESLint + tsc） |

---

## 📁 專案結構

```
agentic-rag-customer-service/
├── apps/
│   ├── backend/                # Python FastAPI — DDD 4-Layer
│   │   ├── src/
│   │   │   ├── domain/         # 領域層：Entity, VO, Repository Interface
│   │   │   ├── application/    # 應用層：Use Case, Command/Query
│   │   │   ├── infrastructure/ # 基礎設施：DB, Milvus, LangGraph, arq
│   │   │   └── interfaces/     # 介面層：FastAPI Router, CLI
│   │   ├── migrations/         # DDL SQL 檔（五步流程）
│   │   └── tests/              # pytest-bdd (unit / integration / e2e)
│   └── frontend/               # React + Vite SPA
│       ├── src/
│       │   ├── App.tsx         # React Router v6 路由定義
│       │   ├── routes/paths.ts # 路由常數集中管理
│       │   ├── pages/          # 頁面元件（lazy-loaded）
│       │   ├── components/     # 共用元件 (shadcn/ui + layout)
│       │   ├── features/       # 功能模組（chat / bot / knowledge / auth ...）
│       │   ├── hooks/queries/  # TanStack Query hooks
│       │   ├── stores/         # Zustand stores
│       │   └── constants/      # 共用常數（usage categories 等 SSOT）
│       └── e2e/                # Playwright + playwright-bdd
├── infra/                      # Docker Compose + schema.sql
├── data/                       # 種子資料、測試文件
├── docs/                       # 架構文件 + architecture journal
├── scripts/                    # 架構圖產生、資料操作腳本
├── Makefile                    # 統一指令入口
└── CLAUDE.md                   # 開發規範（DDD / BDD / TDD）
```

---

## 🧪 測試策略

```
        /  E2E  \          Playwright (前端) / pytest-bdd (後端)
       / Integr. \         MSW (前端) / httpx + 真實 DB (後端)
      /   Unit    \        Vitest (前端) / pytest + AsyncMock (後端)
```

| 比例 | 覆蓋率門檻 |
|------|-----------|
| Unit 60% : Integration 30% : E2E 10% | **80%**（POC 階段暫降 70%） |

> **開發流程**：Stage 0 Issue → Stage 1 DDD 設計 → **Stage 2 BDD 先寫 feature** → **Stage 3 TDD 紅燈** → Stage 4 實作 → Stage 5 驗證交付

### E2E 測試執行與影片錄製

#### 前置安裝

```bash
# 1. 安裝 Playwright 瀏覽器（首次使用時）
cd apps/frontend
npx playwright install --with-deps chromium

# 2. 安裝 ffmpeg（合併影片用）
# Ubuntu / Debian
sudo apt install -y ffmpeg

# macOS
brew install ffmpeg

# 無 sudo 權限（下載靜態二進位檔）
curl -L https://johnvansickle.com/ffmpeg/releases/ffmpeg-release-amd64-static.tar.xz -o /tmp/ffmpeg.tar.xz
mkdir -p ~/bin
tar -xf /tmp/ffmpeg.tar.xz -C /tmp
cp /tmp/ffmpeg-*-amd64-static/ffmpeg ~/bin/ffmpeg
chmod +x ~/bin/ffmpeg
# 確認安裝：~/bin/ffmpeg -version
```

#### 執行 E2E 測試（含影片錄製）

```bash
cd apps/frontend

# 1. 從 Feature 檔案產生 spec
npx bddgen

# 2. 執行全部 E2E 測試（影片自動錄製，設定於 playwright.config.ts video: "on"）
npx playwright test

# 僅執行 auth + journey 測試
npx playwright test --project=auth --project=journeys

# 僅執行 journey 測試
npx playwright test --project=journeys
```

影片會存放在 `apps/frontend/test-results/<測試名稱>/video.webm`。

#### 合併所有影片為單一 MP4

```bash
cd apps/frontend

# 1. 產生影片清單檔
find test-results -name "video.webm" -not -path "*retry*" | sort | \
  sed 's/^/file /' > /tmp/ffmpeg_concat.txt

# 2. 合併為 MP4
ffmpeg -y -f concat -safe 0 -i /tmp/ffmpeg_concat.txt \
  -c:v libx264 -preset fast -crf 23 -pix_fmt yuv420p \
  -movflags +faststart e2e-all-tests.mp4

# 產出：apps/frontend/e2e-all-tests.mp4
```

> **提示**：`-not -path "*retry*"` 會排除 retry 影片，僅保留每個測試的首次執行。若要包含 retry 影片，移除該條件即可。

#### 檢視測試報告

```bash
# HTML 互動式報告（含影片嵌入 + 截圖 + Trace）
npx playwright show-report

# 檢視單一失敗測試的操作軌跡
npx playwright show-trace test-results/<測試目錄>/trace.zip
```

---

## 📝 文件

| 文件 | 說明 |
|------|------|
| [`CLAUDE.md`](./CLAUDE.md) | 開發規範：DDD 架構、測試策略、Git 工作流 |
| [`DEVELOPMENT_PLAN.md`](./DEVELOPMENT_PLAN.md) | Sprint 開發計畫 (S0–S7 + Enterprise + Token-Gov) |
| [`SPRINT_TODOLIST.md`](./SPRINT_TODOLIST.md) | Sprint 進度追蹤（checkbox） |
| [`docs/architecture-journal.md`](./docs/architecture-journal.md) | 架構學習筆記（非 trivial 任務後追加） |
| [`docs/`](./docs/) | 架構設計文件 |
| [`.claude/rules/`](./.claude/rules/) | 開發自動化規則（DDD / 測試 / 安全 / Migration） |

---

## 📄 授權

MIT License
