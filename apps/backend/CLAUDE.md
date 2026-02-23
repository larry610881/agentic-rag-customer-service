# Backend — DDD 4-Layer FastAPI + LangGraph

## 架構概覽

```
src/
├── domain/                # 領域層（核心，不依賴外層）
│   ├── tenant/            # 租戶管理
│   │   ├── entity.py      # Tenant Entity
│   │   ├── value_objects.py
│   │   └── repository.py  # TenantRepository Interface (ABC)
│   ├── knowledge/         # 知識庫管理
│   │   ├── entity.py      # Document, Chunk Entity
│   │   ├── value_objects.py
│   │   └── repository.py  # KnowledgeRepository Interface
│   ├── rag/               # 檢索增強生成
│   │   ├── services.py    # VectorSearchService Interface
│   │   └── value_objects.py
│   ├── conversation/      # 對話管理
│   │   ├── entity.py      # Conversation, Message Entity
│   │   └── repository.py
│   └── agent/             # Agent 編排
│       ├── entity.py      # Tool Definition Entity
│       └── services.py    # AgentService Interface
├── application/           # 應用層（Use Case 編排）
│   ├── tenant/
│   │   └── create_tenant_use_case.py
│   ├── knowledge/
│   │   ├── upload_document_use_case.py
│   │   └── query_knowledge_use_case.py
│   ├── rag/
│   │   └── query_rag_use_case.py
│   └── conversation/
│       └── send_message_use_case.py
├── infrastructure/        # 基礎設施層（外部服務實作）
│   ├── db/                # SQLAlchemy ORM + Repository Impl
│   ├── qdrant/            # Qdrant Vector DB
│   ├── embedding/         # OpenAI / Azure Embedding
│   ├── langgraph/         # LangGraph Agent + Tools
│   ├── cache/             # Redis Cache
│   └── external/          # 外部 API Adapter
└── interfaces/            # 介面層（HTTP / CLI 入口）
    ├── api/               # FastAPI Router
    │   ├── tenant_router.py
    │   ├── knowledge_router.py
    │   ├── conversation_router.py
    │   └── deps.py        # 共用依賴（auth, current_user）
    └── cli/               # Typer CLI Command
```

## DDD 分層紅線

| 規則 | 說明 |
|------|------|
| Domain 禁止依賴外層 | `domain/` 不可 import `application/`、`infrastructure/`、`interfaces/` |
| Domain 禁止框架依賴 | `domain/` 不可 import SQLAlchemy、FastAPI、LangGraph |
| Application 禁止 Infra 具體 | `application/` 透過 Interface 注入，不可 import `infrastructure/` class |
| Interfaces 禁止業務邏輯 | Router 只做 HTTP 轉換，委派給 Application |
| Infrastructure 實作 Domain 介面 | `QdrantKnowledgeRepo` 實作 `KnowledgeRepositoryInterface` |

## 套件管理

```bash
uv sync                    # 安裝依賴
uv add <package>           # 新增套件
uv add --dev <package>     # 新增開發套件
uv run <command>           # 執行指令
```

## 測試

```bash
# 全量測試
uv run python -m pytest tests/ -v --tb=short

# 覆蓋率
uv run python -m pytest tests/ --cov=src --cov-report=term-missing

# 指定範圍
uv run python -m pytest tests/unit/knowledge/ -v

# Lint
uv run ruff check src/
uv run mypy src/
```

### 測試目錄結構

```
tests/
├── features/              # BDD Feature 檔案
│   ├── unit/
│   │   ├── tenant/
│   │   ├── knowledge/
│   │   └── rag/
│   ├── integration/
│   └── e2e/
├── unit/                  # Unit step definitions（鏡像 features/unit/）
│   ├── tenant/
│   ├── knowledge/
│   └── rag/
├── integration/           # Integration tests
└── conftest.py
```

### 關鍵測試規則

- **pytest-bdd v8**：step definitions 必須是 `def`（非 `async def`）
- **async 包裝**：`asyncio.get_event_loop().run_until_complete(coro)`
- **Unit Test**：必須用 `AsyncMock` mock Repository，禁止真實 DB
- **Feature 路徑**：從 `tests/features/` 起算（`pyproject.toml` 設定 `bdd_features_base_dir`）
- **覆蓋率門檻**：80%

## DI Container

- 使用 `dependency-injector`
- 所有 Repository 和 Use Case 在 Container 註冊
- Interfaces 層透過 `@inject` + `Depends(Provide[Container.xxx])` 注入
