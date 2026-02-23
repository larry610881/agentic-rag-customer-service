---
paths:
  - "apps/backend/**/*.py"
---

# Python 開發規則（編輯 .py 檔時自動套用）

## DDD 4-Layer 程式碼層級

### src/domain/ (領域層)
- 定義 Entity、Value Object、Domain Event、Repository Interface
- **禁止** import `application/`、`infrastructure/`、`interfaces/`
- **禁止** import SQLAlchemy、FastAPI、LangGraph
- 純 Python + pydantic，不依賴任何外部框架

### src/application/ (應用層)
- 定義 Use Case（Command/Query Handler）
- 透過 Repository Interface 操作 Domain 物件
- **禁止** import `infrastructure/` 的具體實作
- **禁止** import SQLAlchemy、FastAPI

### src/infrastructure/ (基礎設施層)
- 實作 Domain 定義的 Repository Interface
- 包含 DB、Qdrant、LangGraph、外部 API Adapter
- **允許** import SQLAlchemy、Qdrant client、LangGraph

### src/interfaces/ (介面層)
- FastAPI Router、CLI Command、Event Handler
- 只負責 HTTP/CLI 轉換，委派給 Application 層
- Service/Use Case 必須透過 DI Container 注入

## DDD 各層測試對照表

| 層級 | 測試類型 | 測什麼 | Mock 策略 |
|------|---------|--------|-----------|
| **Domain** | Unit | Entity 行為、VO 驗證、Domain Service | 無需 Mock（純邏輯） |
| **Application** | Unit | Use Case 邏輯、Command/Query 處理 | AsyncMock(spec=RepoInterface) |
| **Application** | Integration | Use Case + 真實 DB | 真實 Repository |
| **Infrastructure** | Integration | Repository 實作、DB 查詢 | 真實 DB / testcontainer |
| **Interfaces** | Integration | API 端點、認證、格式 | httpx.AsyncClient |

## Unit Test 紅線（違反即修正）

以下行為在 `tests/unit/` 目錄下**一律禁止**：

- ❌ 禁止使用 `db_session` fixture 進行真實 DB 操作
- ❌ 禁止直接實例化 Repository：`XxxRepository(db=db_session)`
- ❌ 禁止 `db_session.execute()` / `db_session.add()` / `db_session.commit()`
- ❌ 禁止 `from sqlalchemy import` 或 `from sqlalchemy.future import`（conftest.py 除外）
- ✅ 必須用 `AsyncMock(spec=XxxRepository)` mock Repository 層
- ✅ 必須用 `AsyncMock` / `MagicMock` mock Infrastructure 層

## pytest-bdd v8 Step Definition 完整範例

```python
"""租戶知識庫查詢 BDD Step Definitions"""
import asyncio
from types import SimpleNamespace
from datetime import datetime, timezone
from unittest.mock import AsyncMock

import pytest
from pytest_bdd import given, scenarios, then, when

from src.application.knowledge.query_knowledge_use_case import QueryKnowledgeUseCase

# 從 tests/features/ 起算的相對路徑
scenarios("unit/knowledge/query_knowledge.feature")


def _run(coro):
    """同步包裝 async 呼叫（pytest-bdd v8 step 必須是 def，不可 async def）"""
    loop = asyncio.get_event_loop()
    return loop.run_until_complete(coro)


@pytest.fixture
def context():
    return {}


@given("租戶 {string} 的知識庫中有文件資料")
def setup_knowledge_data(context, string):
    mock_knowledge_repo = AsyncMock()
    mock_knowledge_repo.search_by_tenant = AsyncMock(return_value=[
        SimpleNamespace(
            id="doc-1",
            tenant_id=string,
            title="退貨政策",
            content="30 天內可退貨",
            score=0.95,
            created_at=datetime.now(timezone.utc),
        ),
    ])
    mock_embedding_service = AsyncMock()
    mock_embedding_service.embed_query = AsyncMock(return_value=[0.1] * 1536)

    context["use_case"] = QueryKnowledgeUseCase(
        knowledge_repo=mock_knowledge_repo,
        embedding_service=mock_embedding_service,
    )
    context["tenant_id"] = string
    context["mock_knowledge_repo"] = mock_knowledge_repo


@when("我查詢 {string}", target_fixture="result")
def query_knowledge(context, string):
    return _run(context["use_case"].execute(
        tenant_id=context["tenant_id"],
        query=string,
    ))


@then("應回傳相關的知識庫文件")
def verify_result(result):
    assert len(result.documents) >= 1
    assert result.documents[0].title == "退貨政策"


@then("回傳結果應包含 tenant_id 過濾")
def verify_tenant_isolation(context):
    context["mock_knowledge_repo"].search_by_tenant.assert_called_once()
    call_args = context["mock_knowledge_repo"].search_by_tenant.call_args
    assert call_args.kwargs.get("tenant_id") == context["tenant_id"]
```

## Mock 策略總表

| 依賴 | Unit Test | Integration Test | E2E Test |
|------|-----------|-----------------|----------|
| **MySQL (DB)** | ❌ AsyncMock | ✅ Docker MySQL | ✅ Docker MySQL |
| **Redis** | ❌ AsyncMock | ✅ Docker Redis | ✅ Docker Redis |
| **Qdrant** | ❌ AsyncMock | ✅ Docker Qdrant / testcontainer | ✅ Docker Qdrant |
| **Repository 層** | ❌ AsyncMock(spec=Interface) | ✅ 真實 Repository | ✅ 真實 Repository |
| **Infrastructure 層** | ❌ AsyncMock | 視服務而定 | 視服務而定 |
| **OpenAI/Embedding API** | ❌ AsyncMock | ❌ Mock（固定向量） | ⚠️ Sandbox |
| **LangGraph** | ❌ AsyncMock | ⚠️ 部分 Mock | ✅ 真實 |

## 測試範圍定義

### Unit Test — 防守範圍：Domain + Application 邏輯
| 項目 | 說明 |
|------|------|
| **測什麼** | Entity 行為、Use Case 編排、Command/Query 處理、Schema 驗證 |
| **不測什麼** | SQL 正確性、API 路由、DB 連線、向量搜尋精確度 |
| **速度期望** | 極快（< 1 秒/scenario） |

### Integration Test — 防守範圍：API 端點 + DB + 向量 DB
| 項目 | 說明 |
|------|------|
| **測什麼** | HTTP → Middleware → Use Case → Repository → DB → HTTP 完整流程 |
| **不測什麼** | Domain 內部邊界條件（Unit Test 責任） |
| **速度期望** | 中等（< 5 秒/scenario） |

## Feature 路徑定位（全域統一）

`pyproject.toml` 設定 `bdd_features_base_dir = "tests/features/"`：

```python
# ✅ 正確：從 tests/features/ 起算
scenarios("unit/knowledge/query_knowledge.feature")

# ❌ 禁止：../、Path(__file__)
scenarios("../../../features/unit/knowledge/query_knowledge.feature")
```

## 測試金字塔比例

```
Unit : Integration : E2E ≈ 60% : 30% : 10%
```

## Definition of Done（每個功能模組）

- [ ] Feature 檔案已建立（unit + integration）
- [ ] Unit Test 覆蓋所有 Use Case 公開方法 + happy path + ≥2 error paths
- [ ] Integration Test 覆蓋所有端點的 200/401/404/422
- [ ] E2E feature + step_defs 已撰寫（核心業務流程）
- [ ] `uv run python -m pytest tests/ -v` 全部 pass
- [ ] 覆蓋率 ≥ 80%
- [ ] 無 ruff / mypy 錯誤
