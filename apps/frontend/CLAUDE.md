# Frontend — React + Vite SPA

## 架構概覽

```
src/
├── App.tsx                # React Router 路由定義
├── main.tsx               # React 入口（createRoot + BrowserRouter）
├── globals.css            # Tailwind CSS + shadcn/ui 主題
├── routes/
│   └── paths.ts           # 路由常數集中管理
├── pages/                 # 頁面元件（lazy-loaded）
│   ├── login.tsx
│   ├── chat.tsx
│   ├── bots.tsx
│   ├── bot-detail.tsx
│   ├── knowledge.tsx
│   ├── knowledge-detail.tsx
│   ├── feedback.tsx
│   ├── feedback-browser.tsx
│   ├── feedback-conversation.tsx
│   └── settings-providers.tsx
├── components/            # 共用 UI 元件
│   ├── layout/            # AppShell, Sidebar, Header, ProtectedRoute
│   └── ui/                # shadcn/ui 元件（禁止修改）
├── features/              # 功能模組
│   ├── chat/              # AI 對話
│   │   ├── components/    # ChatInput, MessageBubble, ConversationList
│   │   ├── hooks/         # useStreaming
│   │   └── types.ts
│   ├── knowledge/         # 知識庫
│   │   ├── components/    # DocumentList, UploadDropzone
│   │   └── hooks/
│   ├── feedback/          # 回饋分析
│   │   └── components/
│   ├── bot/               # 機器人管理
│   │   └── components/
│   ├── settings/          # 系統設定
│   │   └── components/
│   └── auth/              # 認證
│       ├── components/    # LoginForm
│       └── hooks/
├── hooks/                 # 共用 hooks
│   └── queries/           # TanStack Query hooks
├── lib/                   # 工具函式
│   ├── api-client.ts      # fetch 封裝
│   └── utils.ts           # cn() 等工具
├── stores/                # Zustand stores
├── constants/             # 常數定義
└── test/                  # 測試基礎設施
    ├── setup.ts           # Vitest 全域設定
    ├── test-utils.tsx     # renderWithProviders
    ├── fixtures/          # Mock 資料
    └── mocks/             # MSW handlers
        ├── handlers.ts
        └── server.ts
```

## Vite SPA 慣例

- **純 Client-side SPA**，無 SSR / SSG
- **路由**：React Router v6，定義在 `src/App.tsx`，常數在 `src/routes/paths.ts`
- **頁面**放 `src/pages/`，使用 `React.lazy()` 做 code-splitting
- **佈局**：`ProtectedRoute`（auth guard） + `AppShell`（sidebar + header + Outlet）
- **環境變數**使用 `VITE_` 前綴，透過 `import.meta.env.VITE_*` 存取

## shadcn/ui 慣例

- 元件安裝至 `src/components/ui/`
- **禁止修改** `src/components/ui/` 下的原始元件
- 客製化請包裝新元件
- 使用 `cn()` 合併 className

## 常用指令

```bash
npm run dev                # 開發伺服器（http://localhost:5173）
npm run build              # 建置（產出 dist/ 靜態檔）
npm run preview            # 預覽 build 產出
npm run test               # Vitest 全部測試
npm run test:coverage      # 覆蓋率報告
npm run test:e2e           # E2E BDD 測試（bddgen + Playwright）
npm run lint               # ESLint 檢查
```

## 測試

### 測試金字塔

| 層級 | 工具 | 檔案命名 | 比例 |
|------|------|---------|------|
| Unit | Vitest + RTL | `*.test.tsx` | 60% |
| Integration | Vitest + RTL + MSW | `*.integration.test.tsx` | 30% |
| E2E | playwright-bdd | `e2e/features/**/*.feature` | 10% |

### 關鍵測試規則

- **查詢元素**：`getByRole` > `getByLabelText` > `getByText` > `getByTestId`
- **互動**：使用 `userEvent`（禁止 `fireEvent`）
- **MSW**：Integration Test 使用 MSW 攔截 HTTP
- **E2E**：使用 `playwright-bdd`，POM 透過 Playwright fixtures 注入
- **覆蓋率門檻**：80%

### E2E 目錄結構

```
e2e/
├── features/{domain}/*.feature  # Feature 檔案
├── steps/
│   ├── fixtures.ts              # createBdd(test) + POM
│   ├── common/                  # 共用步驟
│   └── {domain}/*.steps.ts      # Step Definitions
├── pages/*.ts                   # Page Objects
└── .features-gen/               # 自動產生（gitignore）
```

## 程式碼風格

- **Functional Components only**，禁止 Class Components
- **named exports**（非 default export）— 頁面元件除外（需 default export for lazy loading）
- **禁止 `any`**，使用 `unknown` 或精確型別
- **Tailwind CSS**：className 按邏輯分組
- **Zustand**：一個 feature 一個 store
- **TanStack Query**：hooks 放 `src/hooks/queries/`，queryKey 陣列格式
