# Frontend — Next.js 15 App Router

## 架構概覽

```
src/
├── app/                   # Next.js App Router
│   ├── layout.tsx         # Root layout
│   ├── page.tsx           # Home / Login
│   ├── (auth)/            # 認證相關頁面
│   │   └── login/
│   ├── (dashboard)/       # 需認證的頁面
│   │   ├── chat/          # AI 對話頁面
│   │   ├── knowledge/     # 知識庫管理
│   │   └── settings/      # 系統設定
│   └── api/               # API Routes（BFF）
├── components/            # 共用 UI 元件
│   └── ui/                # shadcn/ui 元件（禁止修改）
├── features/              # 功能模組
│   ├── chat/              # AI 對話
│   │   ├── components/    # ChatInput, MessageBubble, ConversationList
│   │   ├── hooks/         # useConversation, useMessages
│   │   └── types.ts
│   ├── knowledge/         # 知識庫
│   │   ├── components/    # DocumentList, UploadForm
│   │   └── hooks/
│   └── auth/              # 認證
│       ├── components/    # LoginForm
│       └── hooks/
├── hooks/                 # 共用 hooks
│   └── queries/           # TanStack Query hooks
├── lib/                   # 工具函式
│   ├── api-client.ts      # Axios 或 fetch 封裝
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

## Next.js App Router 慣例

- **Server Components** 為預設，需要互動性才加 `'use client'`
- **頁面**放 `src/app/{route}/page.tsx`
- **Layout** 放 `src/app/{route}/layout.tsx`
- **環境變數**使用 `NEXT_PUBLIC_` 前綴（Client-side 可見）
- **API Route** 放 `src/app/api/{route}/route.ts`

## shadcn/ui 慣例

- 元件安裝至 `src/components/ui/`
- **禁止修改** `src/components/ui/` 下的原始元件
- 客製化請包裝新元件
- 使用 `cn()` 合併 className

## 常用指令

```bash
npm run dev                # 開發伺服器（http://localhost:3000）
npm run build              # 建置
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
- **named exports**（非 default export）
- **禁止 `any`**，使用 `unknown` 或精確型別
- **Tailwind CSS**：className 按邏輯分組
- **Zustand**：一個 feature 一個 store
- **TanStack Query**：hooks 放 `src/hooks/queries/`，queryKey 陣列格式
