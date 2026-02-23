---
paths:
  - "apps/frontend/**/*.ts"
  - "apps/frontend/**/*.tsx"
---

# TypeScript 開發規則（編輯 .ts/.tsx 時自動套用）

## 程式碼風格

- 使用 2 空格縮排
- 使用分號結尾，單引號優先
- **只使用 Functional Components**，禁止 Class Components
- **禁止使用 `any`**，改用 `unknown` 或精確型別
- 使用 **named exports**（非 default export）
- 元件 props 必須定義獨立的 type

```tsx
type UserProfileProps = {
  userId: string;
  onEdit: (id: string) => void;
};

export const UserProfile = ({ userId, onEdit }: UserProfileProps) => {
  // ...
};
```

## 命名慣例

| 對象 | 命名方式 | 範例 |
|------|---------|------|
| 元件 | PascalCase | `UserProfile` |
| 函式 / 變數 | camelCase | `fetchUserData` |
| 型別 / 介面 | PascalCase | `UserProfileProps` |
| 常數 | UPPER_SNAKE_CASE | `MAX_RETRY_COUNT` |
| 自訂 Hook | camelCase + use 前綴 | `useConversation` |
| 事件處理 | handle 前綴 | `handleSubmit` |

## Next.js App Router 慣例

- 頁面放 `src/app/{route}/page.tsx`
- Layout 放 `src/app/{route}/layout.tsx`
- Server Components 為預設，需要互動性才加 `'use client'`
- API Route 放 `src/app/api/{route}/route.ts`
- 環境變數使用 `NEXT_PUBLIC_` 前綴（Client-side 可見）

## 前端測試金字塔（60:30:10）

| 層級 | 工具 | 用途 | 比例 |
|------|------|------|------|
| Unit | Vitest + RTL | 元件渲染、hook 邏輯、store | 60% |
| Integration | Vitest + RTL + MSW | 元件與 API 互動 | 30% |
| E2E | playwright-bdd | 真實 API 合約驗證 | 10% |

## Vitest + RTL Unit Test 範例

```tsx
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { ChatInput } from './ChatInput';

describe('ChatInput', () => {
  const mockOnSend = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('應正確渲染輸入框和送出按鈕', () => {
    render(<ChatInput onSend={mockOnSend} />);
    expect(screen.getByRole('textbox')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '送出' })).toBeInTheDocument();
  });

  it('送出訊息應呼叫 onSend 並清空輸入', async () => {
    const user = userEvent.setup();
    render(<ChatInput onSend={mockOnSend} />);

    await user.type(screen.getByRole('textbox'), '你好');
    await user.click(screen.getByRole('button', { name: '送出' }));

    expect(mockOnSend).toHaveBeenCalledWith('你好');
  });

  it('空訊息不應觸發送出', async () => {
    const user = userEvent.setup();
    render(<ChatInput onSend={mockOnSend} />);

    await user.click(screen.getByRole('button', { name: '送出' }));

    expect(mockOnSend).not.toHaveBeenCalled();
  });
});
```

### 查詢元素優先順序（強制）

1. `getByRole` — 最優先（語義化查詢）
2. `getByLabelText` — 表單元素
3. `getByPlaceholderText` — 無 label 時
4. `getByText` — 顯示文字
5. `getByTestId` — **最後手段**，需註明原因

### 互動慣例
- **使用 `userEvent`**（禁止 `fireEvent`）
- 每個 `it` 只測一件事
- 測試使用者可見的行為，禁止測試內部 state

## MSW Integration Test 範例

```tsx
// src/test/mocks/handlers/conversation.ts
import { http, HttpResponse } from 'msw';

export const conversationHandlers = [
  http.get('/api/conversations', () => {
    return HttpResponse.json([
      { id: '1', title: '退貨查詢', lastMessage: '請問退貨流程？' },
    ]);
  }),

  http.post('/api/conversations/:id/messages', async ({ request }) => {
    const body = await request.json();
    return HttpResponse.json({
      id: 'msg-1',
      content: 'AI 回覆：您可以在 30 天內申請退貨...',
      role: 'assistant',
    });
  }),
];
```

```tsx
// ChatPage.integration.test.tsx
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, it, expect } from 'vitest';
import { server } from '@/test/mocks/server';
import { http, HttpResponse } from 'msw';
import { ChatPage } from './ChatPage';
import { renderWithProviders } from '@/test/test-utils';

describe('ChatPage 整合測試', () => {
  it('應從 API 載入對話列表', async () => {
    renderWithProviders(<ChatPage />);

    expect(await screen.findByText('退貨查詢')).toBeInTheDocument();
  });

  it('API 回傳 500 應顯示錯誤訊息', async () => {
    server.use(
      http.get('/api/conversations', () => {
        return HttpResponse.json(null, { status: 500 });
      })
    );

    renderWithProviders(<ChatPage />);

    expect(await screen.findByText('載入失敗')).toBeInTheDocument();
  });
});
```

## test-utils.tsx 範例（App Router Provider 包裝）

```tsx
// src/test/test-utils.tsx
import { render, type RenderOptions } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';

const createTestQueryClient = () =>
  new QueryClient({
    defaultOptions: {
      queries: { retry: false },
    },
  });

export const renderWithProviders = (
  ui: React.ReactElement,
  options?: RenderOptions
) => {
  const queryClient = createTestQueryClient();
  return render(
    <QueryClientProvider client={queryClient}>
      {ui}
    </QueryClientProvider>,
    options
  );
};
```

## 每個元件必須覆蓋

| 場景 | 說明 |
|------|------|
| Happy Path | 正常渲染、正常互動 |
| Loading 狀態 | 載入中顯示 skeleton / spinner |
| Error 狀態 | API 錯誤顯示錯誤訊息 |
| Empty 狀態 | 無資料時的空狀態 UI |
| 使用者互動 | 點擊、輸入、送出表單 |

## Zustand Store 慣例

- 一個 feature 一個 store
- Store 檔案放在 `src/stores/`
- Action 與 state 分離

## TanStack Query 慣例

- Query hooks 放 `src/hooks/queries/`
- queryKey 使用陣列格式且集中管理
- 分離 query 與 mutation

## Definition of Done

- [ ] Unit Test 覆蓋所有元件 props + happy path + ≥2 error paths
- [ ] Integration Test 覆蓋所有 API 端點的 200/401/404/422
- [ ] E2E Feature + Step Definitions 已撰寫（核心流程）
- [ ] `npm run test` 全部通過
- [ ] 覆蓋率 ≥ 80%
- [ ] 無 ESLint / TypeScript 錯誤
