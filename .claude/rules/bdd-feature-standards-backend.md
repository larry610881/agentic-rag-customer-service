---
paths:
  - "apps/backend/tests/**/*.feature"
---

# 後端 BDD Feature 檔撰寫規範

## 語言要求

### 關鍵字：保留 Gherkin 英文
- `Feature`, `Scenario`, `Scenario Outline`, `Given`, `When`, `Then`, `And`, `But`, `Examples`, `Background`

### 描述內容：必須使用繁體中文
- ✅ 正確：`Given 租戶 "T001" 的知識庫中有文件資料`
- ❌ 錯誤：`Given tenant "T001" has documents in knowledge base`

## 檔案結構範例

```gherkin
Feature: 租戶知識庫查詢 (Tenant Knowledge Query)
    身為租戶管理員
    我想要查詢知識庫中的文件
    以便回答客戶的問題

    Background:
        Given 租戶 "T001" 已建立知識庫

    Scenario: 成功查詢相關文件
        Given 租戶 "T001" 的知識庫中有文件資料
        When 我查詢 "退貨政策"
        Then 應回傳相關的知識庫文件
        And 回傳結果應包含 tenant_id 過濾

    Scenario: 查詢無結果
        When 我查詢 "不存在的主題 XYZ"
        Then 應回傳空的文件列表
        And 應包含友善的提示訊息
```

## 目錄結構與鏡像原則

```
apps/backend/tests/
├── features/                    # Feature 檔案
│   ├── unit/
│   │   ├── knowledge/
│   │   │   └── query_knowledge.feature
│   │   └── tenant/
│   │       └── create_tenant.feature
│   ├── integration/
│   │   └── knowledge/
│   │       └── knowledge_api.feature
│   └── e2e/
│       └── rag_flow.feature
├── unit/                        # Unit step definitions（鏡像 features/unit/）
│   ├── knowledge/
│   │   └── test_query_knowledge_steps.py
│   └── tenant/
│       └── test_create_tenant_steps.py
├── integration/                 # Integration step definitions
│   └── knowledge/
│       └── test_knowledge_api.py
└── conftest.py
```

### 規則
- `tests/unit/` 的子目錄結構**必須**鏡像 `tests/features/unit/`
- `tests/integration/` 的子目錄結構**必須**鏡像 `tests/features/integration/`
- 每個新子目錄必須包含 `__init__.py`

## Feature 路徑定位（全域統一）

`pyproject.toml` 設定：

```toml
[tool.pytest.ini_options]
bdd_features_base_dir = "tests/features/"
```

所有 `scenarios()` 和 `@scenario()` 的路徑從 `tests/features/` 起算：

```python
# ✅ 正確
scenarios("unit/knowledge/query_knowledge.feature")

@scenario("unit/tenant/create_tenant.feature", "成功建立新租戶")
def test_create_tenant(): pass

# ❌ 禁止
scenarios("../../../features/unit/knowledge/query_knowledge.feature")
```

## pytest-bdd v8 完整範例

### `scenarios()` 用法（載入整個 Feature）

```python
"""知識庫查詢 BDD Step Definitions"""
import asyncio
from types import SimpleNamespace
from datetime import datetime, timezone
from unittest.mock import AsyncMock

import pytest
from pytest_bdd import given, scenarios, then, when

from src.application.knowledge.query_knowledge_use_case import QueryKnowledgeUseCase

scenarios("unit/knowledge/query_knowledge.feature")


def _run(coro):
    loop = asyncio.get_event_loop()
    return loop.run_until_complete(coro)


@pytest.fixture
def context():
    return {}


@given("租戶 {string} 已建立知識庫")
def tenant_exists(context, string):
    context["tenant_id"] = string


@given("租戶 {string} 的知識庫中有文件資料")
def setup_knowledge(context, string):
    mock_repo = AsyncMock()
    mock_repo.search_by_tenant = AsyncMock(return_value=[
        SimpleNamespace(id="doc-1", tenant_id=string, title="退貨政策",
                        content="30天內可退貨", score=0.95,
                        created_at=datetime.now(timezone.utc)),
    ])
    mock_embedding = AsyncMock()
    mock_embedding.embed_query = AsyncMock(return_value=[0.1] * 1536)

    context["use_case"] = QueryKnowledgeUseCase(
        knowledge_repo=mock_repo, embedding_service=mock_embedding,
    )
    context["mock_repo"] = mock_repo


@when("我查詢 {string}", target_fixture="result")
def query(context, string):
    return _run(context["use_case"].execute(
        tenant_id=context["tenant_id"], query=string,
    ))


@then("應回傳相關的知識庫文件")
def verify_docs(result):
    assert len(result.documents) >= 1
```

### `@scenario()` 裝飾器用法（載入單一 Scenario）

```python
from pytest_bdd import scenario

@scenario("unit/tenant/create_tenant.feature", "成功建立新租戶")
def test_create_tenant():
    pass
```

### async step 包裝方式

pytest-bdd v8 的 step definition **必須是 `def`**，不可 `async def`：

```python
# ✅ 正確：用 _run() 同步包裝
def _run(coro):
    loop = asyncio.get_event_loop()
    return loop.run_until_complete(coro)

@when("我發送查詢請求", target_fixture="result")
def send_query(context):
    return _run(context["use_case"].execute(query="test"))

# ❌ 錯誤：不可直接 async def
@when("我發送查詢請求", target_fixture="result")
async def send_query(context):
    return await context["use_case"].execute(query="test")
```

## 場景撰寫原則

- 每個 Feature 至少包含：1 個 Happy Path + 1 個錯誤路徑
- 使用 `Background` 抽取共用前置條件
- 使用 `Scenario Outline` + `Examples` 處理參數化場景
- 步驟描述應從**使用者/業務角度**出發，避免描述實作細節

```gherkin
# ✅ 好的寫法（業務角度）
When 我上傳文件到知識庫
Then 文件應成功建立並可被搜尋

# ❌ 不好的寫法（實作細節）
When 呼叫 upload_document use case
Then Qdrant collection 應有新的 point
```
