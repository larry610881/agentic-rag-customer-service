# Frontend — Next.js 15 App Router

Agentic RAG Customer Service 前端應用，使用 Next.js 15 App Router + shadcn/ui + Zustand + TanStack Query。

## Getting Started

```bash
npm install
npm run dev
```

Open [http://localhost:3000](http://localhost:3000) with your browser.

## Testing

### Unit / Integration Tests (Vitest)

```bash
npm run test              # 全部 Vitest 測試
npm run test:coverage     # 含覆蓋率報告
```

### E2E BDD Tests (Playwright)

> 前置條件：後端必須在 `http://127.0.0.1:8000` 運行

```bash
# 基本執行（含截圖）
npm run test:e2e

# 或手動步驟
npx bddgen                                    # 從 .feature 產生 spec
npx playwright test                            # 執行全部 10 scenarios
```

### E2E 報告模式

```bash
# HTML 報告（含截圖 + trace 快照）
npx playwright test --trace on --reporter=html
npx playwright show-report --host 0.0.0.0 --port 9323

# HTML 報告 + 影片錄製（每個 scenario 產生 mp4）
npx playwright test --trace on --reporter=html
# 需先在 playwright.config.ts 設定 video: "on"
npx playwright show-report --host 0.0.0.0 --port 9323

# Trace Viewer（逐步 DOM 快照，可拖曳 timeline）
npx playwright test --trace on
npx playwright show-trace test-results/*/trace.zip
```

### E2E 報告操作說明

1. 開啟 HTML 報告後，點擊任一綠色 scenario
2. 底部的 **Traces** 區塊，點擊 trace 檔案進入 Trace Viewer
3. Trace Viewer 功能：
   - 左側：每個 action（goto, fill, click, waitFor）的列表
   - 右側：該 action 當下的頁面截圖
   - 上方 timeline：拖曳可瀏覽每一刻的畫面變化
   - 下方分頁：Network / Console / Source

### E2E Scenarios (10 個)

| Feature | Scenario | 描述 |
|---------|----------|------|
| Login | 成功登入並導向聊天頁 | 輸入帳密 → 登入成功 → 跳轉 /chat |
| Login | 空白欄位顯示驗證錯誤 | 不輸入直接送出 → 顯示驗證訊息 |
| Login | 錯誤帳號顯示失敗訊息 | 錯誤帳號 → 顯示失敗提示 |
| Tenant Isolation | 切換租戶後隔離 | 切換租戶 → 看不到其他租戶的 KB |
| Agent Chat | 發送訊息並收到回覆 | 送出訊息 → AI 回覆 |
| Agent Chat | Streaming 逐字回答 | 送出訊息 → 串流回覆 → 完整顯示 |
| RAG Query | 發送問題並收到回覆 | 送出問題 → AI 回覆 |
| Knowledge CRUD | 登入後瀏覽知識庫列表 | 登入 → 看到 KB 列表 |
| Knowledge CRUD | 查看知識庫詳情頁面 | 點擊 KB → 進入詳情頁 |
| Document Upload | 知識庫詳情頁顯示上傳區域 | 進入詳情頁 → 看到上傳區域 |

## Tech Stack

- **Framework**: Next.js 15 (App Router)
- **UI**: shadcn/ui (Tailwind CSS + Radix UI)
- **Client State**: Zustand
- **Server State**: TanStack Query
- **Form**: React Hook Form + Zod
- **Unit Test**: Vitest + React Testing Library
- **E2E Test**: Playwright + playwright-bdd
