# 新增 Next.js Component

根據指定的元件名稱，生成完整的 Next.js 元件檔案、型別定義與測試檔案，遵循專案既有模式。

## 使用方式

```
/component <元件名稱> [--feature <功能模組名稱>]
```

## 範例

```
/component ChatInput
/component ConversationList --feature conversation
/component KnowledgeUpload --feature knowledge
/component MessageBubble --feature chat
```

## 流程

根據 `$ARGUMENTS` 指定的元件名稱，執行以下步驟：

### 步驟一：分析專案模式

1. 檢查 `apps/frontend/src/components/` 與 `apps/frontend/src/features/` 目錄結構
2. 閱讀既有元件，了解專案慣用模式
3. 判斷元件歸屬：
   - 若帶有 `--feature` 參數，建立在 `apps/frontend/src/features/[feature]/components/`
   - 若為通用 UI 元件，建立在 `apps/frontend/src/components/`

### 步驟二：建立元件檔案

```tsx
// apps/frontend/src/features/[feature]/components/[ComponentName].tsx

type [ComponentName]Props = {
  // 根據元件用途定義 props
};

export const [ComponentName] = ({ ...props }: [ComponentName]Props) => {
  return (
    // JSX — 使用 shadcn/ui 元件
  );
};
```

### 步驟三：建立測試檔案

在元件同層建立測試檔案：

```tsx
// [ComponentName].test.tsx
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, it, expect, vi } from 'vitest';
import { [ComponentName] } from './[ComponentName]';

describe('[ComponentName]', () => {
  it('應正確渲染', () => {
    render(<[ComponentName] />);
    // 基本渲染斷言
  });

  // Happy Path + Error + Empty + Loading 狀態
});
```

### 步驟四：執行測試

```bash
cd apps/frontend && npx vitest run [測試檔案路徑] --reporter=verbose
```

### 步驟五：完成報告

輸出已建立的檔案列表與元件使用範例：

```tsx
import { [ComponentName] } from '@/features/[feature]/components/[ComponentName]';

<[ComponentName] prop1="value" />
```
