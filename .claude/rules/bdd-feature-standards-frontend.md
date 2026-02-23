---
paths:
  - "apps/frontend/e2e/**/*.feature"
---

# 前端 BDD Feature 檔撰寫規範

> Unit/Integration 測試使用純 Vitest（TDD），不使用 BDD/Cucumber。
> 此規範僅適用於 E2E 層的 `.feature` 檔案。

## 語言要求

### 關鍵字：保留 Gherkin 英文
- `Feature`, `Scenario`, `Scenario Outline`, `Given`, `When`, `Then`, `And`, `But`, `Background`, `Examples`

### 描述內容：使用繁體中文

```gherkin
Feature: AI 客服對話
  作為電商客戶
  我希望能夠與 AI 客服對話
  以便快速得到問題的解答

  Background:
    Given 使用者已登入系統

  Scenario: 成功發送對話訊息
    Given 使用者在對話頁面
    When 使用者輸入訊息 "請問退貨流程？"
    And 使用者點擊送出按鈕
    Then 應該顯示 AI 回覆
    And 回覆應包含退貨相關資訊

  Scenario: 空訊息不可送出
    Given 使用者在對話頁面
    When 使用者點擊送出按鈕
    Then 送出按鈕應為停用狀態
```

## 目錄結構

E2E 資源統一放在 `apps/frontend/e2e/` 目錄下，使用 `playwright-bdd`。

```
apps/frontend/e2e/
├── features/
│   ├── auth/
│   │   └── login.feature
│   ├── conversation/
│   │   └── chat.feature
│   └── knowledge/
│       └── upload.feature
├── steps/
│   ├── fixtures.ts                    ← createBdd(test) + POM fixtures
│   ├── common/
│   │   └── visual.steps.ts           ← 共用步驟（視覺回歸）
│   ├── auth/
│   │   └── login.steps.ts            ← 鏡像 features/auth/
│   └── conversation/
│       └── chat.steps.ts
├── pages/                             ← Page Objects
│   ├── LoginPage.ts
│   └── ChatPage.ts
└── .features-gen/                     ← 自動產生（gitignore）
```

### 規則
- `e2e/steps/` 的子目錄結構**必須**鏡像 `e2e/features/`
- **禁止**在 `src/` 下建立 `.feature` 或 step definition 檔案
- E2E 共用步驟放在 `e2e/steps/common/`

## playwright-bdd POM Fixtures 完整範例

### fixtures.ts — 定義 POM fixtures 並匯出 Given/When/Then

```typescript
// e2e/steps/fixtures.ts
import { test as base, createBdd } from 'playwright-bdd';
import { LoginPage } from '../pages/LoginPage';
import { ChatPage } from '../pages/ChatPage';
import { KnowledgePage } from '../pages/KnowledgePage';

export const test = base.extend<{
  loginPage: LoginPage;
  chatPage: ChatPage;
  knowledgePage: KnowledgePage;
}>({
  loginPage: async ({ page }, use) => { await use(new LoginPage(page)); },
  chatPage: async ({ page }, use) => { await use(new ChatPage(page)); },
  knowledgePage: async ({ page }, use) => { await use(new KnowledgePage(page)); },
});

export const { Given, When, Then } = createBdd(test);
```

### Page Object Model（強制）

```typescript
// e2e/pages/ChatPage.ts
import { type Page, type Locator } from '@playwright/test';

export class ChatPage {
  readonly messageInput: Locator;
  readonly sendButton: Locator;
  readonly messageList: Locator;

  constructor(private page: Page) {
    this.messageInput = page.getByRole('textbox', { name: '輸入訊息' });
    this.sendButton = page.getByRole('button', { name: '送出' });
    this.messageList = page.getByRole('list', { name: '對話訊息' });
  }

  async goto() {
    await this.page.goto('/chat');
  }

  async sendMessage(message: string) {
    await this.messageInput.fill(message);
    await this.sendButton.click();
  }
}
```

### Step Definition 範例

```typescript
// e2e/steps/conversation/chat.steps.ts
import { expect } from '@playwright/test';
import { Given, When, Then } from '../fixtures';

Given('使用者在對話頁面', async ({ chatPage }) => {
  await chatPage.goto();
});

When('使用者輸入訊息 {string}', async ({ chatPage }, message: string) => {
  await chatPage.messageInput.fill(message);
});

When('使用者點擊送出按鈕', async ({ chatPage }) => {
  await chatPage.sendButton.click();
});

Then('應該顯示 AI 回覆', async ({ chatPage }) => {
  const lastMessage = chatPage.messageList.locator('[data-role="assistant"]').last();
  await expect(lastMessage).toBeVisible();
});

Then('回覆應包含退貨相關資訊', async ({ chatPage }) => {
  const lastMessage = chatPage.messageList.locator('[data-role="assistant"]').last();
  await expect(lastMessage).toContainText('退貨');
});
```

## E2E 執行流程

```bash
# 1. 從 Feature 檔案產生 spec 檔案
npx bddgen

# 2. 執行 Playwright 測試
npx playwright test

# 3. 更新視覺回歸基準
npx bddgen && npx playwright test --update-snapshots
```

## 視覺回歸步驟

```gherkin
Scenario: 對話頁面視覺回歸
  Given 使用者已登入系統
  And 使用者在對話頁面
  Then 頁面截圖應與基準一致 "chat-page"
```

```typescript
// e2e/steps/common/visual.steps.ts
import { expect } from '@playwright/test';
import { Then } from '../fixtures';

Then('頁面截圖應與基準一致 {string}', async ({ page }, name: string) => {
  await expect(page).toHaveScreenshot(`${name}.png`);
});
```

## E2E 原則

- 使用 Playwright 內建等待機制，**禁止 `waitForTimeout()`**
- 優先使用 accessible locators（`getByRole`, `getByLabel`）
- 每個測試獨立，不依賴其他測試的狀態
- POM 透過 Playwright fixtures 注入，**禁止手動 `new Page()`**
- 從 `e2e/steps/fixtures.ts` 匯入 `Given`/`When`/`Then`（非 `@cucumber/cucumber`）
- 使用 `expect` 從 `@playwright/test` 匯入（非 `vitest`）
