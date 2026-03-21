# ADR: 向量資料庫選型分析與多 VectorStore 架構方案

- **Status**: Accepted (分析報告，無程式碼改動)
- **Date**: 2026-03-20
- **Context**: 系統目前使用 Qdrant 作為唯一向量資料庫，需評估主流方案差異與未來多 VectorStore 架構可行性

---

## 一、主流向量資料庫比較

### 對照表

| 維度 | **Qdrant** | **Milvus** | **Faiss** | **Weaviate** | **Pinecone** | **pgvector** |
|------|-----------|-----------|-----------|-------------|-------------|-------------|
| **類型** | 獨立服務 | 獨立服務 | Library（嵌入式） | 獨立服務 | 全託管 SaaS | PostgreSQL 擴充 |
| **部署** | Docker/Cloud | Docker/K8s/Cloud | pip install | Docker/Cloud | 全託管 | 現有 PostgreSQL |
| **語言** | Rust | Go + C++ | C++ (Python binding) | Go | N/A | C |
| **向量索引** | HNSW | IVF/HNSW/DiskANN | IVF/HNSW/PQ/Flat | HNSW | 專有 | IVF/HNSW |
| **Payload 過濾** | 原生（索引級） | 原生（標量索引） | 需自建 | 原生 | 原生 | SQL WHERE |
| **多租戶隔離** | Payload filter / namespace | Partition key | 手動管理 | Multi-tenancy 原生 | Namespace | SQL Row-Level |
| **Hybrid Search** | Sparse + Dense | Sparse + Dense | 不支援 | BM25 + Dense | 支援 | tsvector + ivfflat |
| **水平擴展** | Sharding + Replication | 分散式原生 | 不支援（單機） | Sharding | 自動 | 靠 PostgreSQL |
| **百萬級延遲** | ~10ms | ~10ms | ~1ms（記憶體） | ~15ms | ~20ms | ~50ms+ |
| **億級能力** | 需 sharding | 原生分散式 | 需 GPU/分片 | 需 sharding | 支援 | 效能下降明顯 |
| **運維複雜度** | 低（單 binary） | 高（etcd+minio+pulsar） | 無（嵌入式） | 中 | 零（SaaS） | 極低（現有 DB） |
| **成本** | 免費/Cloud 付費 | 免費/Cloud 付費 | 免費 | 免費/Cloud 付費 | 付費 | 免費 |
| **gRPC** | 支援 | 支援 | N/A | 支援 | 不支援 | N/A |

### 各自最強場景

| 資料庫 | 最適合 | 不適合 |
|--------|--------|--------|
| **Qdrant** | 中小規模 RAG、豐富 payload 過濾、快速上手 | 億級超大規模 |
| **Milvus** | 大規模生產環境、分散式、企業級 | 小團隊/簡單場景（運維太重） |
| **Faiss** | 離線批次處理、極致低延遲、嵌入式場景 | 需要 CRUD/過濾/持久化 |
| **Weaviate** | GraphQL API、物件導向查詢 | 對延遲要求極高 |
| **Pinecone** | 零運維、快速 MVP | 成本敏感、資料主權要求 |
| **pgvector** | 已有 PostgreSQL、向量量小（< 100 萬）、想少一個服務 | 百萬級以上、高 QPS |

---

## 二、業務場景選型指南

### 決策流程

```
向量資料量？
├── < 100 萬
│   ├── 已有 PostgreSQL？ → pgvector（最省事）
│   └── 否 → Qdrant（輕量好用）
├── 100 萬 ~ 1 億
│   ├── 需要分散式？ → Milvus / Pinecone
│   └── 否
│       ├── 延遲 < 5ms → Faiss（嵌入式）
│       └── 延遲 < 50ms → Qdrant
└── > 1 億 → Milvus / Pinecone
```

### 按業務類型推薦

| 業務場景 | 推薦 | 理由 |
|----------|------|------|
| **電商客服 RAG**（本專案） | **Qdrant** | 多租戶 payload filter 原生支援、collection per KB 天然隔離、中小規模效能足夠 |
| **企業知識庫（百萬文件）** | Milvus / Qdrant Cloud | 需要水平擴展 + partition key |
| **即時推薦系統** | Faiss + Redis 快取 | 超低延遲、純相似度計算 |
| **多模態搜尋（圖+文）** | Milvus / Weaviate | 原生支援多向量欄位 |
| **MVP / POC** | pgvector 或 Pinecone | 最快上線、零運維 |
| **合規/資料主權** | Qdrant / Milvus 自建 | 資料不出境 |

---

## 三、一套系統接多個向量資料庫的架構

### 現有架構優勢

系統已透過 DDD 依賴反轉具備切換基礎：

```
Domain Layer:     VectorStore (ABC)           ← 純介面，不依賴任何 DB
                      ↑                          apps/backend/src/domain/rag/services.py:16-46
Infrastructure:   QdrantVectorStore           ← 唯一實作
                      ↑                          apps/backend/src/infrastructure/qdrant/qdrant_vector_store.py
Container:        providers.Singleton(...)     ← DI 註冊
                                                 apps/backend/src/container.py:588-606
```

VectorStore ABC 定義了 4 個抽象方法：`upsert()`、`ensure_collection()`、`search()`、`delete()`，被 5 個 Use Case 注入使用。

### 方案：Strategy Pattern + Tenant/KB 級別路由

**核心思路**：仿照 `ContentAwareTextSplitterService`（按 content_type 路由到不同 splitter）的 pattern，建立 `RoutingVectorStore` 按租戶或知識庫路由到不同的 vector store 實作。

```
VectorStore (ABC)
    ├── QdrantVectorStore        ← 現有
    ├── PgVectorStore            ← 新增（用現有 PostgreSQL）
    ├── MilvusVectorStore        ← 新增（大規模租戶）
    └── RoutingVectorStore       ← 新增（路由層）
            ↓
        根據 collection name / tenant_id
        路由到對應的 VectorStore 實作
```

### 路由策略

| 策略 | 適用場景 | 實作方式 |
|------|---------|---------|
| **Tenant 級** | 不同租戶用不同 DB | `tenant_id -> VectorStore` mapping |
| **KB 級** | 同租戶不同知識庫用不同 DB | `kb_id -> VectorStore` mapping |
| **Config 級** | 全域預設 + 例外覆蓋 | DB 設定表 + fallback |

### 虛擬碼

```python
class RoutingVectorStore(VectorStore):
    """根據 tenant/KB 路由到不同 VectorStore 實作。"""

    def __init__(
        self,
        default: VectorStore,               # 預設（如 Qdrant）
        overrides: dict[str, VectorStore],   # tenant_id/kb_id -> 特定實作
    ):
        self._default = default
        self._overrides = overrides

    async def search(self, collection, query_vector, ..., filters=None):
        store = self._resolve(collection, filters)
        return await store.search(collection, query_vector, ..., filters)

    def _resolve(self, collection: str, filters: dict | None) -> VectorStore:
        # 從 collection name 解析 kb_id -> 查 mapping
        # 或從 filters["tenant_id"] 查 mapping
        # fallback 到 default
        ...
```

### 需要改動的範圍

| 層級 | 檔案 | 改動 |
|------|------|------|
| Domain | `src/domain/rag/services.py` | **不動**（介面已足夠） |
| Infrastructure | `src/infrastructure/qdrant/` | **不動** |
| Infrastructure | `src/infrastructure/pgvector/` | **新增** PgVectorStore |
| Infrastructure | `src/infrastructure/vector_routing/` | **新增** RoutingVectorStore |
| DI | `src/container.py` | 註冊 routing store + 各實作 |
| Config | `src/config.py` | 新增 vector_store_type / routing config |
| Application | 所有 use case | **不動**（依賴注入的是 VectorStore ABC） |

### 關鍵：Application 層零改動

因為 DDD 架構已經做了依賴反轉：
- 5 個 use case 都注入 `VectorStore` 介面
- 換掉 container 註冊的實作 → 整個系統自動切換
- 加 routing 層 → use case 完全無感

---

## 四、本專案建議

### 現階段（窩廚房電商客服）

**Decision: 繼續使用 Qdrant，不需要更換。**

理由：
- 資料量 < 10 萬 vectors，遠未達 Qdrant 瓶頸
- Payload filter 完美支援多租戶隔離
- gRPC 延遲已經夠低（`prefer_grpc=True` 已啟用）
- 運維最簡單（單 Docker container）

### 未來擴展觸發條件

| 觸發條件 | 行動 |
|----------|------|
| 某租戶向量數 > 500 萬 | 考慮該租戶遷移到 Milvus |
| 想少一個服務 | 小租戶用 pgvector（已有 PostgreSQL） |
| QPS > 1000 且延遲 < 10ms | 考慮 Faiss 快取層 |
| 多模態（圖片搜尋） | 考慮 Milvus 多向量欄位 |

### 多 VectorStore 實作優先順序

1. **pgvector**（最低成本，用現有 DB）
2. **RoutingVectorStore**（路由層）
3. **Milvus**（大規模時才需要）

---

## 五、結論

- 現有 DDD 架構的 `VectorStore` ABC 已提供良好的抽象，切換或新增向量資料庫的成本極低
- 當前場景 Qdrant 是最佳選擇，無需變更
- 未來如需多 VectorStore，採用 Strategy Pattern + RoutingVectorStore 即可，Application 層零改動
- 如果決定實作多 VectorStore 架構，再開新的 plan
