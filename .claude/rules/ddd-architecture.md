---
paths:
  - "apps/backend/src/**/*.py"
---

# DDD 4-Layer 架構規範

## 依賴方向圖

```
┌─────────────────────────────────────────┐
│           Interfaces 層                  │
│   FastAPI Router, CLI, Event Handler     │
│   只負責 HTTP/CLI 轉換，委派給 App 層    │
└──────────────────┬──────────────────────┘
                   ↓ 依賴
┌─────────────────────────────────────────┐
│          Application 層                  │
│   Use Case, Command/Query Handler        │
│   編排 Domain 物件，呼叫 Repository      │
└──────────────────┬──────────────────────┘
                   ↓ 依賴
┌─────────────────────────────────────────┐
│            Domain 層                     │
│   Entity, Value Object, Domain Event     │
│   Repository Interface, Domain Service   │
│   ★ 核心：不依賴任何外層 ★               │
└─────────────────────────────────────────┘
                   ↑ 實作
┌─────────────────────────────────────────┐
│        Infrastructure 層                 │
│   Repository Impl, DB, Qdrant, LangGraph │
│   External API Adapter, Cache            │
│   實作 Domain 定義的介面                 │
└─────────────────────────────────────────┘
```

## 各層可/不可 Import 清單

### Domain 層 (`src/domain/`)
| 可 Import | 不可 Import |
|-----------|------------|
| Python 標準庫 | `application/` |
| pydantic（Value Object） | `infrastructure/` |
| 同 domain 內的其他模組 | `interfaces/` |
| | SQLAlchemy |
| | FastAPI |
| | LangGraph |

### Application 層 (`src/application/`)
| 可 Import | 不可 Import |
|-----------|------------|
| `domain/` 的 Entity, VO, Interface | `infrastructure/` 的具體實作 |
| Python 標準庫 | `interfaces/` |
| | SQLAlchemy |
| | FastAPI |

### Infrastructure 層 (`src/infrastructure/`)
| 可 Import | 不可 Import |
|-----------|------------|
| `domain/` 的 Interface | `application/` |
| SQLAlchemy, Qdrant, LangGraph | `interfaces/` |
| 外部 SDK |  |

### Interfaces 層 (`src/interfaces/`)
| 可 Import | 不可 Import |
|-----------|------------|
| `application/` 的 Use Case | `domain/` 的 Entity 直接操作 |
| `domain/` 的 DTO/Schema | `infrastructure/` 直接操作 |
| FastAPI, Depends | SQLAlchemy |

## 各層 BDD/TDD 測試責任

| 層級 | 測試類型 | 測試重點 | Mock 策略 |
|------|---------|---------|-----------|
| **Domain** | Unit Test | Entity 行為、Value Object 驗證、Domain Service 邏輯 | 無需 Mock（純邏輯） |
| **Application** | Unit + Integration | Use Case 編排邏輯、Command/Query 處理 | Unit: AsyncMock Repository；Integration: 真實 DB |
| **Infrastructure** | Integration | Repository 實作、DB 查詢正確性、Qdrant 操作 | 真實 DB / Qdrant testcontainer |
| **Interfaces** | Integration + E2E | API 端點、Request/Response 格式、認證 | httpx.AsyncClient + 真實 DB |

## 聚合根邊界規則

1. **一個聚合根對應一個 Repository** — `TenantRepository` 管理 `Tenant` 聚合
2. **聚合外部只能透過 ID 引用** — 不可持有其他聚合的 Entity 實例
3. **跨聚合操作透過 Application Service 或 Domain Event** — 禁止直接操作其他聚合的 Repository
4. **聚合內的 Entity 只能透過聚合根存取** — 禁止直接查詢聚合內部 Entity

## 違規掃描規則

### CRITICAL — 必須立即修正
- `domain/` 中 import `infrastructure/`、`interfaces/`、SQLAlchemy
- `application/` 中 import `infrastructure/` 的具體 class
- `interfaces/` 中直接操作 DB session 或 Repository
- Unit Test 中使用真實 DB

### HIGH — 應盡快修正
- Application 層直接回傳 ORM Model（應轉為 Domain DTO）
- Domain Entity 包含 ORM 相關的 annotation
- Infrastructure 層 import Application 層

### MEDIUM — 建議修正
- 過大的 Use Case class（超過 200 行，考慮拆分）
- Domain Event 未被訂閱處理
