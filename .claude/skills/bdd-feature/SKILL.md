# BDD Feature 撰寫

根據需求描述生成 BDD Feature 檔案（英文關鍵字 + 繁中描述），並同時產出 Step Definitions 骨架。自動判斷後端或前端。

## 使用方式

```
/bdd-feature <功能需求描述>
```

## 範例

```
/bdd-feature 租戶知識庫上傳功能
/bdd-feature AI 客服對話流程
/bdd-feature 訂單查詢 RAG 搜尋
/bdd-feature 前端對話頁面 E2E
```

## 流程

根據 `$ARGUMENTS` 描述的功能需求，執行以下步驟：

### 步驟一：需求分析

1. 解析功能需求
2. 判斷歸屬：
   - 包含「前端」、「E2E」、「頁面」→ 前端 E2E（`apps/frontend/e2e/features/`）
   - 其他 → 後端 BDD（`apps/backend/tests/features/`）
3. 識別主要場景（Happy Path + 錯誤路徑）

### 步驟二：撰寫 Feature 檔案

#### 後端

```gherkin
# apps/backend/tests/features/unit/<context>/<feature>.feature
Feature: <功能名稱>
    身為<角色>
    我想要<目標>
    以便<價值>

    Scenario: <成功路徑>
        Given <前置條件>
        When <使用者操作>
        Then <預期結果>

    Scenario: <錯誤路徑>
        Given <前置條件>
        When <錯誤操作>
        Then <錯誤處理>
```

#### 前端 E2E

```gherkin
# apps/frontend/e2e/features/<domain>/<feature>.feature
Feature: <功能名稱>
    作為<角色>
    我希望<目標>
    以便<價值>

    Background:
        Given 使用者已登入系統

    Scenario: <成功路徑>
        Given <前置條件>
        When <使用者操作>
        Then <預期結果>
```

### 步驟三：生成 Step Definitions 骨架

#### 後端（pytest-bdd v8）

```python
# apps/backend/tests/unit/<context>/test_<feature>_steps.py
import asyncio
from unittest.mock import AsyncMock
from pytest_bdd import given, scenarios, then, when

scenarios("unit/<context>/<feature>.feature")

def _run(coro):
    loop = asyncio.get_event_loop()
    return loop.run_until_complete(coro)

@given("<前置條件>", target_fixture="context")
def setup(): ...

@when("<操作>", target_fixture="result")
def action(context): ...

@then("<預期結果>")
def verify(result): ...
```

#### 前端 E2E（playwright-bdd）

```typescript
// apps/frontend/e2e/steps/<domain>/<feature>.steps.ts
import { expect } from '@playwright/test';
import { Given, When, Then } from '../fixtures';

Given('<前置條件>', async ({ page }) => { ... });
When('<操作>', async ({ page }) => { ... });
Then('<預期結果>', async ({ page }) => { ... });
```

### 步驟四：驗證與輸出

1. 確認 Feature 檔案語法正確
2. 列出所有已建立的檔案
3. 說明下一步：可使用 `/tdd` 或 `/ddd-feature` 開始實作
