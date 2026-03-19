# 單租戶建置成本估算（GCP）

> 更新日期：2026-03-15
> 定價基準：GCP us-central1 region，2026/03 公開價格

## 一、基礎設施月費

### 核心服務

| 服務 | GCP 產品 | 規格 | 月費估算 | 備註 |
|------|---------|------|---------|------|
| **Backend API** | Cloud Run | 1 vCPU, 1 GiB, min instances: 0 | ~$0-15 | 按用量計費，idle 時趨近 $0 |
| **PostgreSQL + pgvector** | Cloud SQL | db-custom-1-3840（1 vCPU, 3.75GB RAM）, 20GB SSD | ~$50 | 含自動備份 7 天 |
| **Redis** | Memorystore (Basic) | 1GB | ~$35 | Session / cache / rate limiting |
| **Frontend** | Firebase Hosting | 靜態檔案 | ~$0-5 | 含 CDN，低流量幾乎免費 |
| **VPC Connector** | Serverless VPC Access | — | ~$7 | Cloud Run → Cloud SQL 連線必要 |
| **Container Registry** | Artifact Registry | — | ~$1 | 儲存 Docker image |
| **Logging & Monitoring** | Cloud Logging + Monitoring | — | ~$0-5 | 免費額度通常夠用 |
| **Secret Manager** | Secret Manager | 5-10 secrets | ~$0.5 | API keys 存放 |

### 基礎設施小計

| 項目 | 月費 |
|------|------|
| **最低**（低用量，Cloud Run idle 多） | **~$93** |
| **一般**（中等用量） | **~$108** |
| **高峰**（持續有流量） | **~$113** |

---

## 二、API 費用（LLM + Embedding）

### 用量假設（單租戶，低～中用量）

| 指標 | 低用量 | 中用量 | 高用量 |
|------|-------|-------|-------|
| 每日對話數 | 10 | 50 | 200 |
| 每對話平均 turns | 5 | 5 | 5 |
| 每 turn input tokens | ~2,000 | ~2,000 | ~2,000 |
| 每 turn output tokens | ~500 | ~500 | ~500 |
| 每月 LLM input tokens | ~300K | ~1.5M | ~6M |
| 每月 LLM output tokens | ~75K | ~375K | ~1.5M |
| 每月 Embedding tokens | ~1M | ~5M | ~20M |

### 方案一：最省（GPT-5 nano + Gemini 2.5 Flash-Lite）

| 用途 | 模型 | 月費（低用量） | 月費（中用量） |
|------|------|-------------|-------------|
| Agent 推理 | GPT-5 nano ($0.05/$0.40/M) | ~$0.05 | ~$0.23 |
| 分類/路由 | GPT-5 nano | ~$0.01 | ~$0.05 |
| RAG 生成 | Gemini 2.5 Flash-Lite ($0.10/$0.40/M) | ~$0.06 | ~$0.30 |
| Embedding | text-embedding-3-small ($0.02/M) | ~$0.02 | ~$0.10 |
| **API 小計** | | **~$0.14** | **~$0.68** |

> 適用場景：簡單 FAQ、基礎客服、預算極度有限

### 方案二：推薦（GPT-5 mini 主力 + GPT-5 nano 路由）

| 用途 | 模型 | 月費（低用量） | 月費（中用量） |
|------|------|-------------|-------------|
| Agent 推理 | GPT-5 mini ($0.25/$2.00/M) | ~$0.23 | ~$1.13 |
| 分類/路由 | GPT-5 nano ($0.05/$0.40/M) | ~$0.01 | ~$0.05 |
| RAG 生成 | GPT-5 mini | ~$0.23 | ~$1.13 |
| Embedding | text-embedding-3-small ($0.02/M) | ~$0.02 | ~$0.10 |
| **API 小計** | | **~$0.49** | **~$2.41** |

> 適用場景：一般企業客服，品質與成本平衡

### 方案三：高品質（Claude Sonnet 4.6 + GPT-5 nano 路由）

| 用途 | 模型 | 月費（低用量） | 月費（中用量） |
|------|------|-------------|-------------|
| Agent 推理 | Claude Sonnet 4.6 ($3.00/$15.00/M) | ~$2.03 | ~$10.13 |
| 分類/路由 | GPT-5 nano ($0.05/$0.40/M) | ~$0.01 | ~$0.05 |
| RAG 生成 | Claude Sonnet 4.6 | ~$2.03 | ~$10.13 |
| Embedding | text-embedding-3-small ($0.02/M) | ~$0.02 | ~$0.10 |
| **API 小計** | | **~$4.09** | **~$20.41** |

> 適用場景：高品質需求、複雜推理、客戶要求最佳體驗

---

## 三、總成本組合

### 月費總覽

| 方案 | 基礎設施 | API 費用（低/中用量） | 合計/月 |
|------|---------|---------------------|--------|
| **最省** | ~$93 | ~$0.14 - $0.68 | **~$93 - $94** |
| **推薦（平衡）** | ~$93 | ~$0.49 - $2.41 | **~$93 - $95** |
| **高品質** | ~$93 | ~$4.09 - $20.41 | **~$97 - $113** |

> **關鍵洞察**：單租戶低～中用量下，API 費用佔比極低（< 20%），基礎設施才是主要成本。

### 年費估算

| 方案 | 月費 | 年費 |
|------|------|------|
| **最省** | ~$93-94 | **~$1,116-1,128** |
| **推薦** | ~$93-95 | **~$1,116-1,140** |
| **高品質** | ~$97-113 | **~$1,164-1,356** |

---

## 四、成本優化建議

### 短期（立即可做）

| 優化項目 | 節省幅度 | 說明 |
|---------|---------|------|
| **Committed Use Discount (CUD)** | -20~30% | Cloud SQL 1 年承諾折扣 |
| **Prompt Caching** | -50~90% | 重複 system prompt 快取 |
| **小模型分流** | -80~95% | 簡單任務用 nano/Flash-Lite |

### 中期（規模化後）

| 優化項目 | 節省幅度 | 說明 |
|---------|---------|------|
| **多租戶共享基礎設施** | -50~70% per tenant | 單一 Cloud SQL instance 支撐多租戶 |
| **Cloud Run min instances: 0** | -30~50% | 低用量時段自動縮零 |
| **Batch API** | -50% | 非即時任務（報表、摘要）批次處理 |

### 長期（> 10 租戶後）

| 優化項目 | 節省幅度 | 說明 |
|---------|---------|------|
| **GKE Autopilot** | 取代 Cloud Run | 多服務統一編排，更好的資源利用 |
| **AlloyDB** | 取代 Cloud SQL | 向量搜尋效能更好，但起價更高（~$200/月） |
| **自建 Embedding cache** | -80% embedding cost | 常見查詢 embedding 快取避免重複計算 |

---

## 五、成本 vs 競品比較

| 方案 | 月費 | 對比 |
|------|------|------|
| **本方案（推薦）** | ~$93-95 | — |
| AWS (ECS + RDS + ElastiCache) | ~$110-130 | 類似架構，AWS 稍貴 |
| Azure (Container Apps + Azure DB + Redis) | ~$100-120 | 類似架構 |
| Vercel + Supabase + Upstash | ~$45-70 | 更便宜但 vendor lock-in 更重 |
| Railway / Render | ~$30-50 | 最便宜但 enterprise 功能有限 |

---

## 六、風險與注意事項

1. **Cloud SQL 是最大固定成本**（~$50/月）：低用量時考慮 Supabase（免費方案有 500MB）或 AlloyDB Omni
2. **Memorystore 是第二大固定成本**（~$35/月）：可考慮 Upstash Redis（serverless，按用量計費 ~$0-10/月）替代
3. **API 價格可能變動**：2026 下半年各廠商可能再次降價，建議每季回顧
4. **Gemini 2.0 Flash 即將停用**（2026/06/01）：如果使用此模型需提前遷移至 2.5 Flash

---

## 七、建議方案

**單租戶 MVP 階段推薦配置：**

```
基礎設施：
├── Cloud Run（Backend）      ~$0-15/月
├── Cloud SQL + pgvector      ~$50/月
├── Memorystore Redis 1GB     ~$35/月
├── Firebase Hosting           ~$0-5/月
└── VPC + Registry + Others   ~$8/月

API（推薦方案）：
├── GPT-5 mini（主力推理）     ~$0.5-2/月
├── GPT-5 nano（分類/路由）    ~$0.01-0.05/月
└── text-embedding-3-small     ~$0.02-0.1/月

總計：~$93-108/月
```

> 進入多租戶階段後，每新增租戶的邊際成本主要是 API 費用（~$0.5-20/月），基礎設施可共享。
