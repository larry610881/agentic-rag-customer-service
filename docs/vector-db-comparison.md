# 向量資料庫深入比較：Cloud SQL pgvector vs Qdrant

> 更新日期：2026-03-15

## 一、候選方案概述

| 項目 | Cloud SQL PostgreSQL + pgvector | Qdrant (Self-hosted on GKE/Cloud Run) |
|------|-------------------------------|---------------------------------------|
| 類型 | 關聯式 DB + 向量擴充 | 專用向量資料庫 |
| 託管方式 | GCP Managed Service | Self-hosted（或 Qdrant Cloud） |
| 向量索引 | IVFFlat / HNSW（pgvector 0.7+） | HNSW（高度優化） |
| 結構化查詢 | 原生 SQL | Payload Filter（有限） |
| 維運複雜度 | 低（GCP 託管） | 中～高（需自行管理） |

---

## 二、七維度 Trade-off 分析

### 1. 查詢效能（向量搜尋）

| 指標 | pgvector (HNSW) | Qdrant |
|------|-----------------|--------|
| Recall@10 (1M vectors, 1536d) | ~95-97% | ~98-99% |
| QPS (1M vectors, 1 vCPU) | ~50-100 | ~200-500 |
| P99 Latency | ~20-50ms | ~5-15ms |

**結論**：Qdrant 在純向量搜尋上有 2-5x 效能優勢。但 pgvector 0.7+ 的 HNSW 已大幅縮小差距。

### 2. 混合查詢（向量 + 結構化過濾）

| 場景 | pgvector | Qdrant |
|------|----------|--------|
| `WHERE tenant_id = X AND vector <-> query < threshold` | **原生 SQL，高效** | Payload filter，效能好 |
| 複雜 JOIN（user + order + product） | **原生支援** | 不支援，需外部 DB |
| Full-text search + 向量 | pg_trgm / tsvector 原生整合 | 需外部 Elasticsearch |
| 聚合查詢 (GROUP BY, COUNT) | **原生 SQL** | 不支援 |

**結論**：如果需要大量結構化查詢 + 向量搜尋的混合場景，pgvector 有明顯優勢。

### 3. 擴展性

| 規模 | pgvector | Qdrant |
|------|----------|--------|
| < 1M vectors | ✅ 綽綽有餘 | ✅ 過度設計 |
| 1M - 10M vectors | ✅ 可行，需調優 | ✅ 舒適區 |
| 10M - 100M vectors | ⚠️ 需 read replica + 分區 | ✅ 分散式原生支援 |
| > 100M vectors | ❌ 不建議 | ✅ 水平擴展 |

**轉折點**：約 **10M vectors** 時，pgvector 的管理成本開始顯著上升。

### 4. 營運成本

| 項目 | pgvector (Cloud SQL) | Qdrant (Self-hosted) |
|------|---------------------|---------------------|
| 基礎月費（最小可用） | ~$50（1 vCPU, 3.75GB） | ~$30-70（GKE node 或 Cloud Run） |
| HA 配置 | ~$100（+ read replica） | ~$100-150（3 node cluster） |
| 備份 | Cloud SQL 自動備份（免費 7 天） | 需自行設定（GCS snapshot） |
| 監控 | Cloud Monitoring 整合 | 需自建 Prometheus + Grafana |
| 升級維護 | GCP 自動（minor version） | **手動管理版本升級** |

**結論**：Cloud SQL 的維運成本顯著低於 self-hosted Qdrant。

### 5. 開發體驗

| 項目 | pgvector | Qdrant |
|------|----------|--------|
| ORM 支援 | SQLAlchemy 原生（pgvector extension） | 專用 Python client |
| Migration | Alembic 整合 | Schema-less，無需 migration |
| 學習曲線 | 低（SQL 技能通用） | 中（新 API、新概念） |
| 除錯 | `EXPLAIN ANALYZE` | Dashboard / API logs |

### 6. 生態系整合

| 項目 | pgvector | Qdrant |
|------|----------|--------|
| LangChain | ✅ `PGVector` | ✅ `Qdrant` |
| LlamaIndex | ✅ | ✅ |
| 備份還原 | pg_dump / pg_restore | 自行處理 snapshot |
| 與既有 PostgreSQL 共存 | **同一 DB instance** | 獨立服務 |

### 7. 安全性與合規

| 項目 | pgvector (Cloud SQL) | Qdrant (Self-hosted) |
|------|---------------------|---------------------|
| 加密 at rest | ✅ GCP 預設 | 需自行配置 |
| 加密 in transit | ✅ SSL 預設 | 需自行配置 TLS |
| IAM 整合 | ✅ Cloud SQL IAM | 手動 API key |
| 稽核日誌 | ✅ Cloud Audit Logs | 需自建 |
| SOC2 / ISO 27001 | ✅ GCP 認證涵蓋 | 需自行評估 |

---

## 三、效能 Benchmark 參考

### 測試條件

- 向量維度：1536（text-embedding-3-small）
- 資料量：100K / 500K / 1M vectors
- 機器規格：1 vCPU, 4GB RAM

### 結果（近似值，基於公開 benchmark）

| 資料量 | 指標 | pgvector HNSW | Qdrant |
|--------|------|--------------|--------|
| 100K | QPS | ~200 | ~800 |
| 100K | P99 Latency | ~10ms | ~3ms |
| 500K | QPS | ~100 | ~500 |
| 500K | P99 Latency | ~25ms | ~8ms |
| 1M | QPS | ~60 | ~300 |
| 1M | P99 Latency | ~45ms | ~12ms |

> **注意**：pgvector 0.7+ HNSW 效能已比早期版本提升 3-5x。實際數據依硬體和參數調優而異。

---

## 四、決策矩陣

| 決策因素 | 權重 | pgvector 得分 | Qdrant 得分 |
|---------|------|-------------|------------|
| 向量搜尋效能 | 15% | 7 | 10 |
| 混合查詢能力 | 20% | **10** | 5 |
| 營運複雜度 | 20% | **9** | 5 |
| 成本（單租戶） | 15% | **8** | 6 |
| 擴展性 (>10M) | 10% | 5 | **10** |
| 開發體驗 | 10% | **8** | 7 |
| 安全合規 | 10% | **10** | 6 |
| **加權總分** | **100%** | **8.35** | **6.55** |

---

## 五、建議

### 選 Cloud SQL pgvector 的情境（✅ 推薦用於 agentic-rag）

- 向量數量 < 5M
- 需要混合查詢（tenant 隔離、結構化過濾）
- 團隊已有 PostgreSQL 經驗
- 希望最小化維運成本
- 已經需要 PostgreSQL 存放 business data

### 選 Qdrant 的情境

- 向量數量 > 10M 且持續增長
- 純向量搜尋場景（無需複雜 SQL）
- 需要極致搜尋效能（< 10ms P99）
- 有專人負責 infrastructure 維運

### agentic-rag 專案結論

**選擇 Cloud SQL PostgreSQL + pgvector**，原因：

1. 單租戶向量數量預估 < 500K，pgvector 效能綽綽有餘
2. 已需 PostgreSQL 存放 conversation history、user data、feedback
3. 同一 DB instance 減少基礎設施成本（~$50/月 vs pgvector + Qdrant ~$80-120/月）
4. GCP 託管服務大幅降低維運負擔
5. 混合查詢需求高（tenant 過濾 + 向量搜尋 + 結構化分析）

> **轉折點提醒**：當單租戶向量數量超過 5M 或總平台向量超過 50M 時，應重新評估是否引入專用向量 DB。
