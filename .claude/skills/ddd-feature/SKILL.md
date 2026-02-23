# DDD 功能建立

根據指定的功能需求，按照 DDD 4-Layer 架構生成完整的檔案骨架、BDD Feature、Unit Test。

## 使用方式

```
/ddd-feature <bounded-context> <功能描述>
```

## 範例

```
/ddd-feature tenant create-tenant
/ddd-feature knowledge upload-document
/ddd-feature rag query-knowledge
/ddd-feature agent register-tool
```

## 流程

根據 `$ARGUMENTS` 指定的 bounded context 和功能名稱，執行以下步驟：

### 步驟一：分析需求

1. 解析 bounded context（tenant / knowledge / rag / conversation / agent）
2. 確認功能涉及的 Entity、Value Object、Use Case
3. 掃描既有程式碼，找出可複用的元件

### 步驟二：建立 BDD Feature

在 `apps/backend/tests/features/unit/<context>/` 建立 `.feature` 檔案：

```gherkin
Feature: <功能名稱>
    身為<角色>
    我想要<目標>
    以便<價值>

    Scenario: <Happy Path>
        Given <前置條件>
        When <使用者操作>
        Then <預期結果>
```

### 步驟三：建立 DDD 4-Layer 檔案

按順序建立：

1. **Domain Layer**
   - `apps/backend/src/domain/<context>/entity.py` — Entity
   - `apps/backend/src/domain/<context>/value_objects.py` — Value Object（若需要）
   - `apps/backend/src/domain/<context>/repository.py` — Repository Interface

2. **Application Layer**
   - `apps/backend/src/application/<context>/<use_case>.py` — Use Case

3. **Infrastructure Layer**
   - `apps/backend/src/infrastructure/<impl>/<repository>.py` — Repository Implementation

4. **Interfaces Layer**
   - `apps/backend/src/interfaces/api/<context>_router.py` — FastAPI Router

### 步驟四：建立 Unit Test

在 `apps/backend/tests/unit/<context>/` 建立 step definitions：

```python
import asyncio
from unittest.mock import AsyncMock
from pytest_bdd import given, scenarios, then, when

scenarios("unit/<context>/<feature>.feature")

def _run(coro):
    loop = asyncio.get_event_loop()
    return loop.run_until_complete(coro)

# ... step definitions with AsyncMock
```

### 步驟五：執行測試

```bash
cd apps/backend && uv run python -m pytest tests/unit/<context>/ -v --tb=short
```

### 步驟六：完成報告

輸出已建立的檔案列表與下一步建議。
