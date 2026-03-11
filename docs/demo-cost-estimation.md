# 成本估算 — Demo + 正式環境部署方案比較（參數化版）

> **定價基準日**：2026-03-05
> **部署區域**：asia-east1（台灣彰化）— GCP 服務
> **幣別**：USD（美元）
> **計費基準**：日費（不計算免費額度，算實際費用）

---

## 目錄

- [1. 架構總覽](#1-架構總覽)
- [2. 參數定義](#2-參數定義)
- [3. GCP 基礎設施成本](#3-gcp-基礎設施成本)
- [4. LLM API 成本](#4-llm-api-成本)
- [5. Demo 總成本估算](#5-demo-總成本估算)
  - [5.1 方案 A：GCP 完整部署](#51-方案-agcp-完整部署)
  - [5.2 方案 B：GCP 精簡部署](#52-方案-bgcp-精簡部署)
  - [5.3 方案 C：最低成本 Demo（外部平台）](#53-方案-c最低成本-demo外部平台)
  - [5.4 方案 C-GCP 混合：DB 留 GCP](#54-方案-c-gcp-混合db-留-gcp)
  - [5.5 三方案比較](#55-三方案比較)
  - [5.6 快速估算公式](#56-快速估算公式)
- [5.7 正式環境成本估算](#57-正式環境成本估算)
  - [5.7.1 Backend 選擇：Cloud Run vs GKE](#571-backend-選擇cloud-run-vs-gke)
  - [5.7.2 無 HA 版：單一客戶驗證期](#572-無-ha-版單一客戶驗證期)
  - [5.7.3 HA 版：1-5 家客戶上限成本](#573-ha-版1-5-家客戶上限成本)
- [5.8 容量規劃矩陣：按月流量級距升級](#58-容量規劃矩陣按月流量級距升級)
- [5.9 每租戶 Token 消耗與 1-10 家客戶成本明細（V1 vs V3 對照）](#59-每租戶-token-消耗與-1-10-家客戶成本明細v1-vs-v3-對照)
- [6. 向量資料庫策略 — SaaS 擴展規劃](#6-向量資料庫策略--saas-擴展規劃)
- [7. 定價參考來源](#7-定價參考來源)
- [附錄 A：Token 實測紀錄模板](#附錄-atoken-實測紀錄模板)
- [附錄 B：敏感度分析](#附錄-b敏感度分析)
- [附錄 C：部署前置作業 Checklist](#附錄-c部署前置作業-checklist)
- [附錄 D：自建 vs 外部方案成本對照（18M Token 基準）](#附錄-d自建-vs-外部方案成本對照18m-token-基準)
  - [50,000 TWD 預算對標（全 HA × 定價策略）](#50000-twd-預算對標全-ha--不同使用率--定價策略)
  - [方案總比較：各情境成本與定價矩陣](#方案總比較各情境成本與定價矩陣)

---

## 1. 架構總覽

```mermaid
graph TB
    subgraph Internet
        User["👤 使用者<br/>(瀏覽器)"]
    end

    subgraph GCP["☁️ Google Cloud Platform — asia-east1"]
        subgraph Edge["Edge Layer"]
            LB["⚖️ Cloud Load Balancing<br/>+ Cloud CDN"]
        end

        subgraph Static["Static Hosting"]
            FE["🖥️ Frontend<br/>React SPA 靜態檔<br/><i>Cloud Storage / Cloudflare Pages</i>"]
        end

        subgraph Compute["Compute Layer — Cloud Run"]
            BE["⚙️ Backend<br/>FastAPI + SSE<br/><i>1 vCPU · 512 MiB</i>"]
        end

        subgraph Data["Data Layer"]
            PG["🐘 Cloud SQL<br/>PostgreSQL 16<br/><i>db-f1-micro</i>"]
            Redis["🔴 Memorystore<br/>Redis 7 · 1 GiB"]
            QD["🔮 Qdrant<br/>GCE VM (e2-small)<br/><i>向量資料庫</i>"]
        end
    end

    subgraph External["External APIs"]
        LLM["🤖 OpenAI / DeepSeek / Google / Anthropic<br/>GPT-5.1 · DeepSeek V3.2 · Gemini 2.5<br/><i>生成 + Embedding</i>"]
        LINE["💬 LINE Messaging API<br/><i>Webhook</i>"]
    end

    User -->|HTTPS| LB
    LB -->|靜態資產| FE
    LB -->|API 請求| BE
    BE -->|SQL Query| PG
    BE -->|Rate Limit · Cache| Redis
    BE -->|向量搜尋| QD
    BE -->|LLM 推論 · Embedding| LLM
    BE -->|Webhook 接收| LINE

    style GCP fill:#e8f0fe,stroke:#4285f4,stroke-width:2px
    style Edge fill:#fce8e6,stroke:#ea4335
    style Static fill:#f0f4e6,stroke:#7cb342
    style Compute fill:#e6f4ea,stroke:#34a853
    style Data fill:#fef7e0,stroke:#fbbc04
    style External fill:#f3e8fd,stroke:#a142f4
```

### 部署決策

| 決策點 | 選擇 | 理由 |
|--------|------|------|
| 計算平台 | **Cloud Run**（非 GKE） | Demo 規模無需 K8s；Cloud Run 支援 SSE 串流；按需計費更省 |
| Backend WebSocket | **不需要分開部署** | 目前使用 SSE（非 WebSocket），標準 HTTP 即可，無需 sticky session |
| Qdrant | **GCE VM 自建** | GCP 無託管 Qdrant；stateful 服務需 persistent disk，VM 最穩定（詳見第 6 章） |
| 前端託管 | **Cloud Storage + CDN** 或 **Cloudflare Pages** | React SPA 純靜態檔，不需 Cloud Run；GCP 內用 Cloud Storage，外部用 Cloudflare Pages（$0） |

---

## 2. 參數定義

> 以下參數請依實際測試數據填入，公式會自動計算。

### 2.1 流量參數

| 參數 | 符號 | 預設值 | 說明 |
|------|------|--------|------|
| 每租戶月訪客數 | `V_month` | **10,000** | 租戶電商平台的月訪客量 |
| 客服使用率 | `P_cs` | **10%** | 訪客中觸發 AI 客服的比例 |
| 月對話數（每租戶） | `C_month` | **1,000** | = V_month × P_cs |
| 每次對話輪數 | `R` | **3** | 實測平均（多數用戶問 1-3 輪即結束） |
| Demo 天數 | `D` | `___` | Demo 展示持續天數 |
| 日活對話佔比 | `P_daily` | 0.1 | 日活 = C_month × P_daily（假設 10% 月活為峰值日活） |
| 每日高峰併發數 | `N_peak` | `___` | 同時在線對話數（可從日活推算） |

### 2.2 Token 參數（實測後填入）

> **測試方式**：用 Demo 情境跑對話，從 LLM API 回應的 `usage` 欄位記錄。
> **2026-03-05 實測結果**：GPT-5.1，3 輪對話（電商客服 RAG 問答）。

| 參數 | 符號 | 實測值 | 說明 |
|------|------|--------|------|
| 每次對話 Input Tokens 總和 | `T_in` | **12,015** | 含 system prompt + RAG context + 歷史對話（3 輪實測） |
| 每次對話 Output Tokens 總和 | `T_out` | **566** | LLM 生成的回答（3 輪實測） |
| 每次對話 Embedding Tokens | `T_emb` | **300** | 每輪查詢 embedding（~100 tokens × 3 輪） |
| 平均對話輪數 | `R` | **3** | 多數用戶問 1-3 輪即結束 |

### 2.3 衍生參數

```
每租戶月對話數 = V_month × P_cs = 10,000 × 10% = 1,000 次

月 LLM Input Tokens  = C_month × T_in  = 1,000 × 12,015 = 12.0M
月 LLM Output Tokens = C_month × T_out = 1,000 × 566    = 0.57M
月 Embedding Tokens   = C_month × T_emb = 1,000 × 300    = 0.30M

Demo 總對話數 = C_month × (D / 30)
Demo LLM Input Tokens  = Demo 總對話數 × T_in
Demo LLM Output Tokens = Demo 總對話數 × T_out
Demo Embedding Tokens   = Demo 總對話數 × T_emb
```

---

## 3. GCP 基礎設施成本

### 3.1 Cloud Run — Backend（FastAPI + SSE）

| 規格 | Demo 配置 | 單價 | 月成本估算 |
|------|-----------|------|-----------|
| vCPU | 1 vCPU | $0.0000336/vCPU-s | 依使用量 |
| 記憶體 | 512 MiB | $0.0000035/GiB-s | 依使用量 |
| 最小實例 | 1（避免冷啟動） | idle 費率 ≈ 1/10 active | **~$10.50/月** |
| 最大實例 | 3 | — | — |
| Request 費 | — | $0.40/百萬 | 可忽略 |

**最小實例持續運行估算**（1 vCPU, 512 MiB, 24/7 idle）：

```
idle vCPU  = 1 × $0.00000336/s × 86400 × 30 = $8.71/月
idle 記憶體 = 0.5 × $0.00000035/s × 86400 × 30 = $0.45/月
合計 idle ≈ $9.16/月

+ 活躍處理時間（依流量，估 10% 時間活躍）
active = $9.16 × 10 × 0.1 = $9.16/月

Backend Cloud Run ≈ $18.32/月
```

### 3.2 Frontend 靜態檔託管

> 前端已從 Next.js SSR 遷移至 React + Vite SPA，只需靜態檔託管，**不再需要 Cloud Run**。

| 方案 | 服務 | 月成本 | 日成本 | 說明 |
|------|------|--------|--------|------|
| GCP 內 | Cloud Storage + CDN | ~$1/月 | ~$0.03/天 | 適合方案 A（全 GCP 合規） |
| 外部 | Cloudflare Pages | $0 | $0 | 純靜態 CDN，無 data 落地，適合方案 B/C |

```
GCP Cloud Storage 估算：
  Storage (< 1 GB)  ≈ $0.02/月
  Egress (10 GB)    ≈ $1.20/月（走 CDN 更便宜）
  靜態檔託管 ≈ $1/月（$0.03/天）

Cloudflare Pages：
  靜態檔託管 = $0（免費方案足夠 Demo 用量）
```

### 3.3 GCE VM — Qdrant（向量資料庫）

> Qdrant 是 stateful 服務，需要 persistent disk。GCE VM 是 GCP 內自建的最佳選擇。
> 詳細分析見 [第 6 章：向量資料庫策略](#6-向量資料庫策略--saas-擴展規劃)。

| 規格 | Demo 配置 | 單價 | 月成本 |
|------|-----------|------|--------|
| VM | e2-small（0.5 vCPU, 2GB RAM） | ~$0.0185/hr | ~$14.50 |
| SSD | 20 GB Balanced PD | $0.11/GB/月 | ~$2.20 |
| Snapshot 備份 | 20 GB | $0.026/GB/月 | ~$0.52 |

```
Qdrant GCE VM ≈ $19/月（asia-east1 含 +10%）
```

### 3.4 Cloud SQL for PostgreSQL

| 規格 | Demo 配置 | 單價 | 月成本 |
|------|-----------|------|--------|
| 實例類型 | db-f1-micro（共享 0.2 vCPU, 0.6GB RAM） | ~$0.0105/hr | **~$7.56/月** |
| 儲存 | 10 GB SSD | $0.222/GB/月 | **$2.22/月** |
| HA | ❌ 不啟用（Demo 不需要） | — | — |
| 備份 | 自動備份 7 天 | 含在內 | — |

```
Cloud SQL ≈ $9.78/月
```

> **注意**：db-f1-micro 無 SLA，適合 Dev/Demo。正式環境建議 db-custom-1-3840（~$83/月）。

### 3.5 Memorystore for Redis

| 規格 | Demo 配置 | 單價 | 月成本 |
|------|-----------|------|--------|
| 等級 | Basic M1 | ~$0.033/GiB-hr | — |
| 容量 | 1 GB | — | **~$24/月** |

```
Memorystore Redis ≈ $24/月
```

> **替代方案**：Cloud Run 內建 in-memory cache（目前程式已有 `InMemoryCacheService`），Demo 可省掉 Redis。**潛在節省：$24/月**。

### 3.6 Cloud Load Balancing + Cloud CDN

| 項目 | 單價 | 月成本 |
|------|------|--------|
| Forwarding Rule（1 條） | $0.025/hr | **$18/月** |
| Data Processing | $0.012/GB | 依流量 |
| CDN Cache Egress（Asia Pacific） | $0.12/GB | 依流量 |
| CDN HTTP 請求 | $0.0075/萬次 | 可忽略 |

```
假設 Demo 月流量 10 GB：
LB data   = 10 × $0.012 = $0.12
CDN egress = 10 × $0.12  = $1.20

LB + CDN ≈ $19.32/月
```

> **替代方案**：Demo 規模可直接用 Cloud Run 內建 URL（自帶 TLS），不設獨立 LB + CDN。**潛在節省：$19.32/月**。

### 3.7 網域

| TLD | 年費 | 月均攤 |
|-----|------|--------|
| .com | $12/年 | **$1/月** |
| .dev | $12/年 | **$1/月** |

```
網域 ≈ $1/月
```

### 3.8 其他固定成本

| 項目 | 月成本 |
|------|--------|
| Artifact Registry（Docker Image 儲存） | ~$0.50（< 5 GB） |
| Static External IP（1 個） | ~$3/月 |
| Network Egress（asia-east1, 10 GB） | ~$1.20 |
| Secret Manager（< 10 secrets） | Free Tier |

```
其他 ≈ $4.70/月
```

---

## 4. LLM API 成本

### 4.1 模型定價比較（2026-03-05 更新）

#### 生成模型

| 模型 | Input / 1M tokens | Output / 1M tokens | 適用場景 |
|------|-------------------|---------------------|---------|
| **OpenAI** | | | |
| GPT-5.2 | $1.75 | $14.00 | 最新旗艦 |
| GPT-5.1 | $1.25 | $10.00 | 旗艦、高性價比 ⭐ 目前使用 |
| GPT-5 | $1.25 | $10.00 | 前代旗艦 |
| GPT-5 Mini | $0.25 | $2.00 | 輕量任務 |
| GPT-5 Nano | $0.05 | $0.40 | 極低成本 |
| **DeepSeek** | | | |
| DeepSeek V3.2 | $0.28 | $0.42 | 極低成本、中文強 |
| DeepSeek R1 | $0.55 | $2.19 | 推理模型 |
| **Google** | | | |
| Gemini 2.5 Flash | $0.30 | $2.50 | 高性價比首選 |
| Gemini 2.5 Flash Lite | $0.10 | $0.40 | 極低成本 |
| Gemini 2.5 Pro | $1.25 | $10.00 | 旗艦推理 |
| **Anthropic** | | | |
| Claude Sonnet 4.6 | $3.00 | $15.00 | Agent 編排 |
| Claude Haiku 4.5 | $1.00 | $5.00 | 輕量任務 |
| Claude Opus 4.6 | $15.00 | $75.00 | 最高品質 |

#### Embedding 模型

| 模型 | 每 1M tokens | 說明 |
|------|-------------|------|
| text-embedding-3-small | $0.02 | 高性價比首選（目前使用） |
| text-embedding-3-large | $0.13 | 較高品質 |

### 4.2 參數化 LLM 成本公式

```
═══════════════════════════════════════════════════════════════
  Demo LLM 成本 = 生成成本 + Embedding 成本

  生成成本 = (Demo總對話數 × T_in / 1,000,000 × Input單價)
           + (Demo總對話數 × T_out / 1,000,000 × Output單價)

  Embedding 成本 = Demo總對話數 × T_emb / 1,000,000 × Embedding單價

  C_month = V_month × P_cs = 10,000 × 10% = 1,000
  Demo總對話數 = C_month × D / 30
═══════════════════════════════════════════════════════════════
```

### 4.3 範例試算（基於 2026-03-05 實測數據）

基於 GPT-5.1 實測 3 輪對話結果：

| 參數 | 實測值 | 說明 |
|------|--------|------|
| `T_in` | 12,015 tokens | 實測 3 輪（含 system prompt + RAG context + 歷史累積） |
| `T_out` | 566 tokens | 實測 3 輪回答總和 |
| `T_emb` | 300 tokens | 3 次查詢 embedding |
| `C_month` | 1,000 次對話/月 | 10,000 訪客 × 10% 使用率 |
| `D` | 7 天 Demo | 假設 |

```
Demo 總對話數 = 1,000 × 7 / 30 ≈ 233 次

┌─────────────────────────────────────────────────────────┐
│ 使用 GPT-5.1（⭐ 目前使用）                              │
│                                                         │
│ Input  = 233 × 12,015 / 1M × $1.25  = $3.50           │
│ Output = 233 × 566    / 1M × $10.00 = $1.32           │
│ Embed  = 233 × 300    / 1M × $0.02  = $0.001          │
│                                                         │
│ LLM 合計 ≈ $4.82                                        │
├─────────────────────────────────────────────────────────┤
│ 使用 GPT-5 Nano（最低成本）                               │
│                                                         │
│ Input  = 233 × 12,015 / 1M × $0.05  = $0.14           │
│ Output = 233 × 566    / 1M × $0.40  = $0.05           │
│ Embed  = 233 × 300    / 1M × $0.02  = $0.001          │
│                                                         │
│ LLM 合計 ≈ $0.19                                        │
├─────────────────────────────────────────────────────────┤
│ 使用 DeepSeek V3.2（極低成本 + 中文強）                    │
│                                                         │
│ Input  = 233 × 12,015 / 1M × $0.28  = $0.78           │
│ Output = 233 × 566    / 1M × $0.42  = $0.06           │
│ Embed  = 233 × 300    / 1M × $0.02  = $0.001          │
│                                                         │
│ LLM 合計 ≈ $0.84                                        │
├─────────────────────────────────────────────────────────┤
│ 使用 Claude Sonnet 4.6                                  │
│                                                         │
│ Input  = 233 × 12,015 / 1M × $3.00  = $8.40           │
│ Output = 233 × 566    / 1M × $15.00 = $1.98           │
│ Embed  = 233 × 300    / 1M × $0.02  = $0.001          │
│                                                         │
│ LLM 合計 ≈ $10.38                                       │
└─────────────────────────────────────────────────────────┘
```

---

## 5. Demo 總成本估算

> 以下所有方案以**日費**計算，不計算免費額度，算實際費用。

### 5.1 方案 A：GCP 完整部署

> 所有服務留在 GCP asia-east1，符合公司全 GCP 資安政策。

| 項目 | 月成本 | 日成本 |
|------|--------|--------|
| Cloud Run — Backend | $18.32 | $0.61 |
| Cloud Storage — Frontend | $1.00 | $0.03 |
| GCE VM — Qdrant | $19.00 | $0.63 |
| Cloud SQL（db-f1-micro） | $9.78 | $0.33 |
| Memorystore Redis | $24.00 | $0.80 |
| Load Balancer + CDN | $19.32 | $0.64 |
| 其他（網域、IP、Registry、Egress） | $5.70 | $0.19 |
| **基礎設施小計** | **$97.12/月** | **$3.24/日** |

```
═══════════════════════════════════════════════
  方案 A — 7 天 Demo 估算

  基礎設施 = $3.24 × 7 = $22.68
  LLM（GPT-5.1, 1K 月對話） = $4.82
  ─────────────────────────────────
  合計 ≈ $27.50
═══════════════════════════════════════════════
```

### 5.2 方案 B：GCP 精簡部署

省去非必要服務，用替代方案降低成本：

| 項目 | 月成本 | 日成本 | 替代策略 |
|------|--------|--------|---------|
| Cloud Run — Backend | $18.32 | $0.61 | 維持 |
| Frontend | $0 | $0 | 使用 Cloud Run 內建 URL 託管靜態檔 |
| Qdrant — GCE VM e2-small | $19.00 | $0.63 | 自建（persistent disk + 備份） |
| Cloud SQL（db-f1-micro） | $9.78 | $0.33 | 維持（最小規格） |
| Memorystore Redis | ~~$24.00~~ → $0 | $0 | 改用 InMemoryCacheService（程式已支援） |
| Load Balancer + CDN | ~~$19.32~~ → $0 | $0 | 直接用 Cloud Run 內建 URL（自帶 TLS） |
| 其他 | $1.50 | $0.05 | 只剩 Artifact Registry |
| **基礎設施小計** | **$48.60/月** | **$1.62/日** | 節省 50% |

```
═══════════════════════════════════════════════
  方案 B — 7 天 Demo 估算

  基礎設施 = $1.62 × 7 = $11.34
  LLM（GPT-5.1, 1K 月對話） = $4.82
  ─────────────────────────────────
  合計 ≈ $16.16
═══════════════════════════════════════════════
```

### 5.3 方案 C：最低成本 Demo（外部平台）

> ⚠️ **公司政策注意**：需確認外部平台是否符合資安合規要求。

#### 核心差異

| | 全 GCP（方案 A/B） | 最低成本（方案 C） |
|---|---|---|
| 公司政策 | ✅ 符合全 GCP 資安政策 | ⚠️ 需確認外部平台是否合規 |
| DB data 位置 | GCP asia-east1 | 外部（Render US / Neon US-East） |
| Qdrant | GCE VM 自建 | **同樣 GCE VM 自建**（正式 data 留 GCP） |

#### 方案 C 架構

| 層 | 服務 | 日費 | 月費參考 | 說明 |
|---|---|---|---|---|
| Frontend | Cloudflare Pages | $0 | $0 | 純靜態 CDN，無 data 落地 |
| Backend | Render Starter | $0.23 | $7 | 支援 Docker + SSE |
| PostgreSQL | Neon Launch | $0.63 | $19 | 付費 Launch plan 確保穩定 |
| Qdrant | GCE VM e2-small | $0.63 | $19 | 與 GCP 方案相同，正式 data 留 GCP |
| Redis | 不需要 | $0 | $0 | InMemoryCacheService |
| LLM | OpenAI / Anthropic | per use | — | 依用量 |
| **基礎設施小計** | | **$1.49/日** | **$45/月** | |

> 若公司要求 DB data 全進 GCP → 見下方 [方案 C-GCP 混合](#54-方案-c-gcp-混合db-留-gcp)

```
═══════════════════════════════════════════════
  方案 C — 7 天 Demo 估算

  基礎設施 = $1.49 × 7 = $10.43
  LLM（GPT-5.1, 1K 月對話） = $4.82
  ─────────────────────────────────
  合計 ≈ $15.25
═══════════════════════════════════════════════
```

> 方案 C 省的主要是 Cloud Run backend（$0.61→$0.23）和 Memorystore（$0.80→$0）

### 5.4 方案 C-GCP 混合：DB 留 GCP

PostgreSQL 留 Cloud SQL、Qdrant 留 GCE VM，只有**無狀態**的 Frontend + Backend 用外部平台：

| 項目 | 服務 | 日費 |
|------|------|------|
| Frontend | Cloudflare Pages | $0 |
| Backend | Render Starter | $0.23 |
| PostgreSQL | **Cloud SQL**（db-f1-micro） | **$0.33** |
| Qdrant | **GCE VM** e2-small | **$0.63** |
| 其他 | — | $0 |
| **日小計** | | **$1.19** |
| **7 天** | | **$8.33** |
| **14 天** | | **$16.66** |

> 這是最安全的混合方案：有狀態的 DB data 留在 GCP 合規，只有無狀態的計算層用外部降成本。

### 5.5 三方案比較

#### 日成本對比（不含 LLM、不含免費額度）

| 項目 | 方案 A（GCP 完整）| 方案 B（GCP 精簡）| 方案 C（最低成本）|
|---|---|---|---|
| Frontend | Cloud Storage $0.03 | Cloud Run URL $0 | Cloudflare Pages $0 |
| Backend（Cloud Run / Render） | $0.61 | $0.61 | $0.23 |
| PostgreSQL（Cloud SQL / Neon） | $0.33 | $0.33 | $0.63 |
| Qdrant GCE VM | $0.63 | $0.63 | $0.63 |
| Redis / Memorystore | $0.80 | $0 | $0 |
| LB + CDN | $0.64 | $0 | $0 |
| 其他（IP, Registry） | $0.19 | $0.05 | $0 |
| **日小計** | **$3.23** | **$1.62** | **$1.49** |
| **7 天 Demo** | **$22.61** | **$11.34** | **$10.43** |
| **14 天 Demo** | **$45.22** | **$22.68** | **$20.86** |

#### 方案選擇指南

| | 方案 A（GCP 完整） | 方案 B（GCP 精簡） | 方案 C（最低成本） | 方案 C-GCP 混合 |
|---|---|---|---|---|
| 日成本 | $3.23 | $1.62 | $1.49 | $1.19 |
| 公司合規 | ✅ 全 GCP | ✅ 全 GCP | ⚠️ 需確認 | ✅ DB 在 GCP |
| 適用場景 | 客戶展示、POC | 內部 Demo | 個人測試 | Demo + DB 合規 |

### 5.6 快速估算公式

```
═══════════════════════════════════════════════════════════════════════════
  Demo 總成本 = 基礎設施日費 × D
              + C_month × (D / 30)
                × [ T_in / 1M × LLM_Input_Price
                  + T_out / 1M × LLM_Output_Price
                  + T_emb / 1M × Embedding_Price ]
═══════════════════════════════════════════════════════════════════════════

基礎設施日費（選擇方案）：
  方案 A（GCP 完整）= $3.24
  方案 B（GCP 精簡）= $1.62
  方案 C（最低成本）= $1.49
  方案 C-GCP 混合   = $1.19

填入你的實測值：

基礎設施日費 = $___
C_month      = ___（月對話數）
D            = ___（Demo 天數）
T_in         = 12,015（每次對話 input tokens，3 輪實測）
T_out        = 566（每次對話 output tokens，3 輪實測）
T_emb        = 300（每次對話 embedding tokens）
LLM 模型     = ___（GPT-5.1 / GPT-5 Nano / DeepSeek V3.2 / Claude Sonnet 4.6）
```

### 5.7 正式環境成本估算

> 正式環境與 Demo 的關鍵差異：**Cloud SQL 升級**（db-f1-micro → db-custom-1-3840）+ **是否啟用 HA**。
> LLM 成本與 Demo 使用相同參數化公式（§4.2），此處只算基礎設施。
> 所有服務限定 GCP asia-east1（符合公司資安政策）。

#### 5.7.1 Backend 選擇：Cloud Run vs GKE

> 1-5 家客戶階段，Backend 該用 Cloud Run 還是 GKE？

```mermaid
graph LR
    Q{"月活對話總數<br/>C_month × N_tenants"}
    CR["☁️ Cloud Run<br/>min-instances=N<br/>按量計費"]
    GKE["☸️ GKE Pod<br/>共用 infra team cluster<br/>固定費用"]

    Q -->|"< 15K<br/>（1-5 家）"| CR
    Q -->|"> 15K 或<br/>已有 GKE 部署"| GKE

    style CR fill:#e6f4ea,stroke:#34a853
    style GKE fill:#e8f0fe,stroke:#4285f4
```

| 維度 | Cloud Run | GKE（共用 cluster） |
|------|-----------|---------------------|
| 月成本（低流量） | **~$18-28** | ~$110+ |
| 月成本（高流量） | 隨流量線性成長 | 固定 |
| 成本模型 | idle 費率 + 用量 | Pod 資源包月 |
| 適合 | **1-5 家客戶、流量不穩定** | 5+ 家、已有 GKE infra |
| 維運 | 零維運 | 需 infra team 協助 |

**流量交叉點**：

```
Cloud Run（request-based, min N instances）：
  月成本 ≈ N × $9.16（idle）+ N × $91.60 × utilization%

GKE Pod（共用 cluster, cluster fee = $0）：
  月成本 ≈ pods × (vCPU × $0.0515/hr + GiB × $0.0057/hr) × 730h

交叉點：utilization > ~35-40% 時 GKE 更便宜
1-5 家客戶 utilization 通常 < 10% → Cloud Run 明顯勝出
```

> **結論：1-5 家客戶階段，Backend 用 Cloud Run。**
> 超過 5 家且流量穩定後，再考慮遷移至 GKE 與 Qdrant 共用 cluster。

#### 5.7.2 無 HA 版：單一客戶驗證期

> Demo 驗證通過 → 第一家付費客戶。接受單點故障，最小化月費。

| 項目 | 服務 | 月成本 | 日成本 | vs Demo Plan B |
|------|------|--------|--------|----------------|
| Frontend | Cloud Storage + CDN | $1 | $0.03 | +$1 |
| Backend | Cloud Run（1 vCPU, 512 MiB, min 1） | $18 | $0.61 | 不變 |
| PostgreSQL | **Cloud SQL db-g1-small** | **~$26** | **~$0.87** | **+$16** |
| Qdrant | GCE VM e2-small | $19 | $0.63 | 不變 |
| 其他 | IP, Registry, Domain | $6 | $0.19 | +$4.50 |
| **基礎設施小計** | | **~$70/月** | **~$2.33/日** | **+$21** |

```
═══════════════════════════════════════════════════════════════
  正式環境（無 HA, Tier 1）日成本公式

  C_prod_noha = $2.33/日

  月成本 = $70 + LLM_monthly

  LLM_monthly = C_month
              × [ T_in/1M × P_in + T_out/1M × P_out + T_emb/1M × P_emb ]
═══════════════════════════════════════════════════════════════
```

> **成本跳躍分析**：Cloud SQL 從 db-f1-micro ($10) → db-g1-small ($26)，增量僅 +$16。
> RAG 機器人 DB 利用率極低（~3%），db-g1-small 足以應付 1-2 家客戶。
> 需更高規格時參考 [§5.8 容量規劃矩陣](#58-容量規劃矩陣按月流量級距升級) 的升級路線。
> 正式定價以 [GCP Calculator](https://cloud.google.com/products/calculator) 確認 asia-east1 區域為準。

#### 5.7.3 HA 版：1-5 家客戶上限成本

> 不能接受服務中斷 → Cloud SQL HA + Qdrant GKE HA。
> 假設公司 infra team 已有 GKE cluster，**cluster fee = $0**（共用攤提）。

| 項目 | 服務 | 月成本 | 日成本 | 說明 |
|------|------|--------|--------|------|
| Frontend | Cloud Storage + CDN | $1 | $0.03 | |
| Backend | Cloud Run（1 vCPU, 1 GiB, min 2） | ~$28 | ~$0.93 | HA：2 min-instances |
| PostgreSQL | **Cloud SQL db-g1-small HA** | **~$52** | **~$1.73** | Regional HA（跨 2 zone，2× 單機） |
| Qdrant | **GKE StatefulSet 2 replicas（共用 cluster）** | **~$91** | **~$3.03** | 含 PVC SSD（詳見 §6.6） |
| 其他 | IP, Registry, Domain | $6 | $0.19 | |
| **基礎設施小計** | | **~$178/月** | **~$5.91/日** | |

```
═══════════════════════════════════════════════════════════════
  正式環境（HA）上限日成本公式

  C_prod_ha = $5.91/日（上限，含 Qdrant 2-replica HA）

  月成本 = $178 + LLM_monthly

  LLM_monthly = C_month × N_tenants
              × [ T_in/1M × P_in + T_out/1M × P_out + T_emb/1M × P_emb ]
═══════════════════════════════════════════════════════════════
```

**5 家客戶月成本試算（GPT-5.1, C_month = 1K/家，基於實測數據）**：

```
基礎設施 = $178/月
LLM = 5 × 1,000 × (12,015/1M × $1.25 + 566/1M × $10.00 + 300/1M × $0.02)
    = 5,000 × $0.02069
    = $103.45/月

月成本 = $178 + $103 = ~$281/月
日成本 = $9.37/日
```

**使用 DeepSeek V3.2 的替代試算（中文客服高性價比選擇）**：

```
LLM = 5 × 1,000 × (12,015/1M × $0.28 + 566/1M × $0.42 + 300/1M × $0.02)
    = 5,000 × $0.00361
    = $18.05/月

月成本 = $178 + $18 = ~$196/月
日成本 = $6.53/日
```

#### 三階段成本對照

| | Demo Plan B | 正式（無 HA） | 正式（HA 上限） |
|---|---|---|---|
| **日成本** | **$1.62** | **$2.33** | **$5.91** |
| 月成本 | $48.60 | $70 | $178 |
| Cloud SQL | db-f1-micro $10 | db-g1-small $26 | db-g1-small HA $52 |
| Qdrant | GCE VM $19 | GCE VM $19 | GKE 2-replica $91 |
| Backend | Cloud Run min 1 | Cloud Run min 1 | Cloud Run min 2 |
| HA | ❌ | ❌ | ✅ |

```mermaid
graph TD
    DEMO["🧪 Demo Plan B<br/>$1.62/日 · $49/月<br/>db-f1-micro + GCE VM"]
    PROD1["🏢 正式（無 HA）<br/>$2.33/日 · $70/月<br/>db-g1-small + GCE VM"]
    PROD2["🛡️ 正式（HA）<br/>$5.91/日 · $178/月<br/>Cloud SQL HA + GKE Qdrant"]

    DEMO -->|"首家客戶付費<br/>升級 Cloud SQL<br/>+$0.71/日"| PROD1
    PROD1 -->|"第 2-5 家客戶<br/>啟用 HA<br/>+$3.58/日"| PROD2

    style DEMO fill:#e6f4ea,stroke:#34a853
    style PROD1 fill:#fef7e0,stroke:#fbbc04
    style PROD2 fill:#fce8e6,stroke:#ea4335
```

> **費用遞增口訣**：Demo ($49) → 首家正式 ($70) → HA 上限 ($178)
> 增量主因：Cloud SQL 升級 (+$16) → HA 雙倍 + Qdrant HA (+$108)

### 5.8 容量規劃矩陣：按月流量級距升級

> 主要變數：`C_total` = 全租戶月對話總數（`C_month × N_tenants`）
> 次要變數：`V_total` = 向量總數（租戶數 × 文件數 × 平均 chunks/文件）

#### 元件瓶頸分析

RAG 機器人每個 turn 只有 ~100ms 在打 DB（12 個簡單 query），其餘 ~10s 都在等 LLM。
真正的升級觸發不是「對話量」，而是以下各元件的實際瓶頸：

| 元件 | 真正的瓶頸 | 為什麼不是對話量？ |
|------|-----------|------------------|
| **Cloud SQL** | DB 連線數 | `pool_size=20` × Cloud Run instances → 連線池常駐佔位 |
| **Qdrant** | RAM（HNSW 向量索引） | 向量數 = 租戶 × 文件 × chunks，跟對話量無關 |
| **Cloud Run** | 併發請求 × 記憶體 | LangGraph state 佔記憶體，併發受 instance memory 限制 |

> **關鍵發現**：`engine.py` 設定 `pool_size=20, max_overflow=30`，每個 Cloud Run instance **常駐 20 個 DB 連線**。
> db-g1-small（~50 連線上限）只能安全支撐 **1-2 個 Cloud Run instance**。

#### 三級距設備規格

```mermaid
graph LR
    T1["🟢 Tier 1：起步<br/>≤ 5K 月對話<br/>1-2 家客戶<br/>~$70/月"]
    T2["🟡 Tier 2：成長<br/>5K-30K 月對話<br/>3-10 家客戶<br/>~$130/月"]
    T3["🔴 Tier 3：規模化<br/>30K-100K 月對話<br/>10-30 家客戶<br/>~$230/月"]

    T1 -->|"Cloud SQL 升級<br/>+ Cloud Run min 2"| T2
    T2 -->|"Qdrant RAM 升級<br/>+ Cloud Run max↑"| T3

    style T1 fill:#e6f4ea,stroke:#34a853
    style T2 fill:#fef7e0,stroke:#fbbc04
    style T3 fill:#fce8e6,stroke:#ea4335
```

| 元件 | Tier 1：起步 | Tier 2：成長 | Tier 3：規模化 |
|------|-------------|-------------|---------------|
| **C_total** | **≤ 5,000** | **5,000 - 30,000** | **30,000 - 100,000** |
| **租戶數** | **1-2 家** | **3-10 家** | **10-30 家** |
| Cloud SQL | db-g1-small ($26) | **⬆ db-custom-1-3840 ($100)** | **⬆ db-custom-2-7680 ($180)** |
| Qdrant | GCE e2-small 2GB ($19) | GCE e2-small 2GB ($19) | **⬆ GCE e2-medium 4GB ($40)** |
| Cloud Run | min 1, max 3, 512MiB ($18) | **⬆ min 2, max 5, 1GiB ($38)** | min 2, max 10, 1GiB ($50) |
| Frontend | Cloud Storage ($1) | Cloud Storage ($1) | Cloud Storage ($1) |
| 其他 | $6 | $6 | $6 |
| **月成本（無 HA）** | **~$70** | **~$164** | **~$277** |
| **日成本（無 HA）** | **~$2.33** | **~$5.47** | **~$9.23** |

#### HA 附加費（選配）

> **Qdrant HA 是可用性問題，不是資料遺失問題。**
> 原始文件存在 PostgreSQL + Cloud Storage，Qdrant 掛掉只需重新 embedding 即可恢復（耗時數分鐘~數小時）。
> 因此 **Qdrant HA 優先級低於 Cloud SQL HA**，可分階段啟用。

| HA 元件 | 附加費 | Tier 1 | Tier 2 | Tier 3 |
|---------|-------|--------|--------|--------|
| Cloud SQL HA | 2× SQL 費用 | — | +$100 | +$180 |
| Qdrant GKE 2-replica | VM→GKE 差價 | — | +$72 | +$96 |
| **含 HA 月成本** | | **$70**（不需要） | **$336** | **$553** |

**建議啟用順序**：

```
Phase 1（Tier 1-2）：無 HA，定期備份
  └─ Cloud SQL：自動備份 7 天（內建免費）
  └─ Qdrant：Snapshot 排程備份（$0.52/月）
  └─ 故障恢復：Cloud SQL ~5 分鐘 / Qdrant 重建向量 ~30 分鐘

Phase 2（Tier 2-3，客戶 SLA 要求時）：僅 Cloud SQL HA
  └─ Cloud SQL HA：+$100-180（自動 failover ~30 秒）
  └─ Qdrant 維持 VM + 備份（掛掉重建向量，可接受）

Phase 3（Tier 3+，完全不能中斷時）：全 HA
  └─ Cloud SQL HA + Qdrant GKE 2-replica
```

#### 完整公式

```
═══════════════════════════════════════════════════════════════════════
  月成本 = Tier 基礎設施 + HA 附加費（選配）+ LLM

  Tier 1 = $70  + $0   + LLM    ← 1-2 家，定期備份即可
  Tier 2 = $164 + $0~172 + LLM  ← 3-10 家，視 SLA 需求啟用 HA
  Tier 3 = $277 + $0~276 + LLM  ← 10-30 家，視 SLA 需求啟用 HA

  LLM = C_total × [ T_in/1M × P_in + T_out/1M × P_out
                   + T_emb/1M × P_emb ]

  C_total = C_month × N_tenants
═══════════════════════════════════════════════════════════════════════
```

#### 各級距升級觸發邊界

##### Tier 1 → Tier 2 觸發條件

| # | 觸發元件 | 監控指標 | 觸發條件 | 原因 |
|---|---------|---------|---------|------|
| 1 | **Cloud Run** | instance 數、冷啟動次數 | 付費客戶上線，需要 HA | min 1 有冷啟動風險 + 單點故障 |
| 2 | **Cloud SQL** | 連線數（`pg_stat_activity`） | Cloud Run ≥ 2 instances | pool_size=20 × 2 = 40 連線，db-g1-small (~50) 飽和 |

> **Tier 1→2 的觸發本質**：不是「流量不夠」，而是「付費客戶需要 SLA」。
> 技術上 Tier 1 撐 5K 月對話毫無壓力，升級是為了可靠性。

##### Tier 2 → Tier 3 觸發條件

| # | 觸發元件 | 監控指標 | 觸發條件 | 原因 |
|---|---------|---------|---------|------|
| 1 | **Qdrant** | RAM 使用率（`/metrics`） | RAM > 80%（向量 ≥ 200K，~1 GB） | HNSW 索引全在 RAM，超限 OOM kill |
| 2 | **Cloud Run** | 同時 instance 數、OOM 事件 | max 5 經常打滿 | 更多租戶 = 更多併發請求 |
| 3 | **Cloud SQL** | CPU 使用率、P99 延遲 | CPU throttle 頻繁 或 P99 > 50ms | 獨立 vCPU → 2 vCPU 確保穩定延遲 |

> **Tier 2→3 的觸發本質**：Qdrant RAM 和 Cloud Run 併發是真正的技術瓶頸。
> Cloud SQL 在此階段更多是預防性升級（dedicated 2 vCPU 防止 throttle）。

#### 各元件流量邊界總覽

```
═══════════════════════════════════════════════════════════════════════

  Cloud SQL 升級邊界（由 Cloud Run instances × pool_size 決定）
  ─────────────────────────────────────────────────
  db-g1-small    (~50 conn)  → 支撐 1-2 Cloud Run instances
  db-custom-1    (~100 conn) → 支撐 2-5 Cloud Run instances
  db-custom-2    (~200 conn) → 支撐 5-10 Cloud Run instances

  💡 可調降 pool_size=5, max_overflow=10（每 instance 15 連線）
     → db-g1-small 可支撐 3 instances，延後升級時間點

  Qdrant 升級邊界（由向量總數 = 租戶 × 文件 × chunks 決定）
  ─────────────────────────────────────────────────
  e2-small  2GB  → ~280K 向量（~1.4 GB）→ ~20 家 × 500 文件 × 25 chunks
  e2-medium 4GB  → ~600K 向量（~3.0 GB）→ ~50 家 × 500 文件 × 25 chunks
  e2-standard-2 8GB → ~1.4M 向量          → ~100+ 家（考慮轉 GKE HA）

  Cloud Run 升級邊界（由 LLM 延遲 × 併發數決定）
  ─────────────────────────────────────────────────
  每個 turn ≈ 10s（LLM 等待），512 MiB 可同時處理 ~8 個 turn
  min 1 max 3  → ~24 併發 turn → ~15K+ 月對話（遠超 Tier 1）
  min 2 max 5  → ~40 併發 turn → ~50K+ 月對話
  min 2 max 10 → ~80 併發 turn → ~100K+ 月對話

  ⚡ Cloud Run 幾乎不會是瓶頸 — LLM API rate limit 才是天花板

═══════════════════════════════════════════════════════════════════════
```

#### 超過 Tier 3：100K+ 月對話

> `C_total > 100K` 時，參考 [§6（向量資料庫策略）](#6-向量資料庫策略--saas-擴展規劃) 評估 GKE 多節點或 Vertex AI。
> 此規模通常已有 30+ 家客戶，基礎設施和 HA 決策需個案評估。

### 5.9 每租戶 Token 消耗與 1-10 家客戶成本明細（V1 vs V3 對照）

> **基準資料來源**：2026-03-05 實測（3 輪對話），詳見 [附錄 A](#附錄-atoken-實測紀錄)
> **流量假設**：每租戶 10,000 訪客/月 × 10% 使用率 = 1,000 次對話/租戶/月
> **三組配置**：V1 原始 → V2 精簡 Prompt → V3 全面優化（推薦）

#### 流量漏斗

```
每租戶月流量：10,000 訪客
        ↓ × 10% 客服使用率
     1,000 次 AI 客服對話
        ↓ × 平均 3 輪/次（實測）
     3,000 輪 LLM 呼叫
```

#### 每租戶每月 Token 消耗量（三組配置對比）

| 指標 | V1 原始 | V2 精簡 Prompt | V3 全面優化 |
|------|--------|---------------|------------|
| 每次對話 Input | 12,015 | 9,563 | 4,931 |
| 每次對話 Output | 566 | 572 | 384 |
| 每次對話 Embed | 300 | 300 | 300 |
| **每次對話合計** | **12,881** | **10,435** | **5,615** |
| **月 Input（1K 對話）** | **12.015M** | **9.563M** | **4.931M** |
| **月 Output（1K 對話）** | **0.566M** | **0.572M** | **0.384M** |
| **月 Embed（1K 對話）** | **0.300M** | **0.300M** | **0.300M** |
| **月合計** | **12.881M** | **10.435M** | **5.615M** |
| **vs V1** | — | **-19%** | **-56%** |

#### 每租戶每月 LLM 成本（V1 原始配置）

| 模型 | Input 成本 | Output 成本 | Embed | **每租戶月費** |
|------|-----------|------------|-------|--------------|
| **GPT-5.1** ⭐ | $15.02 | $5.66 | $0.01 | **$20.69** |
| GPT-5 Nano | $0.60 | $0.23 | $0.01 | **$0.84** |
| DeepSeek V3.2 | $3.36 | $0.24 | $0.01 | **$3.61** |
| Gemini 2.5 Flash | $3.60 | $1.42 | $0.01 | **$5.03** |
| Claude Sonnet 4.6 | $36.05 | $8.49 | $0.01 | **$44.55** |

#### 每租戶每月 LLM 成本（V3 全面優化 — 推薦）

| 模型 | Input 成本 | Output 成本 | Embed | **每租戶月費** | **vs V1** |
|------|-----------|------------|-------|--------------|-----------|
| **GPT-5.1** ⭐ | $6.16 | $3.84 | $0.01 | **$10.01** | **-52%** |
| GPT-5 Nano | $0.25 | $0.15 | $0.01 | **$0.41** | -51% |
| DeepSeek V3.2 | $1.38 | $0.16 | $0.01 | **$1.55** | **-57%** |
| Gemini 2.5 Flash | $1.48 | $0.96 | $0.01 | **$2.45** | -51% |
| Claude Sonnet 4.6 | $14.79 | $5.76 | $0.01 | **$20.56** | -54% |

#### 1-10 家客戶月成本明細（V1 原始 — GPT-5.1，無 HA）

> 基礎設施 Tier 依 §5.8 容量規劃：1-2 家 = Tier 1（$70），3-10 家 = Tier 2（$164）

| 客戶數 | Tier | 基礎設施 | LLM 月費 | **月總成本** | 每家均攤 |
|--------|------|---------|---------|------------|---------|
| 1 | Tier 1 | $70 | $20.69 | **$90.69** | $90.69 |
| 2 | Tier 1 | $70 | $41.38 | **$111.38** | $55.69 |
| 3 | Tier 2 | $164 | $62.07 | **$226.07** | $75.36 |
| 4 | Tier 2 | $164 | $82.76 | **$246.76** | $61.69 |
| 5 | Tier 2 | $164 | $103.45 | **$267.45** | $53.49 |
| 6 | Tier 2 | $164 | $124.14 | **$288.14** | $48.02 |
| 7 | Tier 2 | $164 | $144.83 | **$308.83** | $44.12 |
| 8 | Tier 2 | $164 | $165.52 | **$329.52** | $41.19 |
| 9 | Tier 2 | $164 | $186.21 | **$350.21** | $38.91 |
| 10 | Tier 2 | $164 | $206.90 | **$370.90** | $37.09 |

#### 1-10 家客戶月成本明細（V3 優化 — GPT-5.1，無 HA）⭐ 推薦

| 客戶數 | Tier | 基礎設施 | LLM 月費 | **月總成本** | 每家均攤 | **vs V1** |
|--------|------|---------|---------|------------|---------|-----------|
| 1 | Tier 1 | $70 | $10.01 | **$80.01** | $80.01 | -$10.68 |
| 2 | Tier 1 | $70 | $20.02 | **$90.02** | $45.01 | -$10.68 |
| 3 | Tier 2 | $164 | $30.03 | **$194.03** | $64.68 | -$10.68 |
| 4 | Tier 2 | $164 | $40.04 | **$204.04** | $51.01 | -$10.68 |
| 5 | Tier 2 | $164 | $50.05 | **$214.05** | $42.81 | -$10.68 |
| 6 | Tier 2 | $164 | $60.06 | **$224.06** | $37.34 | -$10.68 |
| 7 | Tier 2 | $164 | $70.07 | **$234.07** | $33.44 | -$10.68 |
| 8 | Tier 2 | $164 | $80.08 | **$244.08** | $30.51 | -$10.68 |
| 9 | Tier 2 | $164 | $90.09 | **$254.09** | $28.23 | -$10.68 |
| 10 | Tier 2 | $164 | $100.10 | **$264.10** | $26.41 | -$10.68 |

#### 1-10 家客戶月成本明細（V1 原始 — DeepSeek V3.2，無 HA）

| 客戶數 | Tier | 基礎設施 | LLM 月費 | **月總成本** | 每家均攤 |
|--------|------|---------|---------|------------|---------|
| 1 | Tier 1 | $70 | $3.61 | **$73.61** | $73.61 |
| 2 | Tier 1 | $70 | $7.22 | **$77.22** | $38.61 |
| 3 | Tier 2 | $164 | $10.83 | **$174.83** | $58.28 |
| 4 | Tier 2 | $164 | $14.44 | **$178.44** | $44.61 |
| 5 | Tier 2 | $164 | $18.05 | **$182.05** | $36.41 |
| 6 | Tier 2 | $164 | $21.66 | **$185.66** | $30.94 |
| 7 | Tier 2 | $164 | $25.27 | **$189.27** | $27.04 |
| 8 | Tier 2 | $164 | $28.88 | **$192.88** | $24.11 |
| 9 | Tier 2 | $164 | $32.49 | **$196.49** | $21.83 |
| 10 | Tier 2 | $164 | $36.10 | **$200.10** | $20.01 |

#### 1-10 家客戶月成本明細（V3 優化 — DeepSeek V3.2，無 HA）⭐ 推薦

| 客戶數 | Tier | 基礎設施 | LLM 月費 | **月總成本** | 每家均攤 | **vs V1** |
|--------|------|---------|---------|------------|---------|-----------|
| 1 | Tier 1 | $70 | $1.55 | **$71.55** | $71.55 | -$2.06 |
| 2 | Tier 1 | $70 | $3.10 | **$73.10** | $36.55 | -$2.06 |
| 3 | Tier 2 | $164 | $4.65 | **$168.65** | $56.22 | -$2.06 |
| 4 | Tier 2 | $164 | $6.20 | **$170.20** | $42.55 | -$2.06 |
| 5 | Tier 2 | $164 | $7.75 | **$171.75** | $34.35 | -$2.06 |
| 6 | Tier 2 | $164 | $9.30 | **$173.30** | $28.88 | -$2.06 |
| 7 | Tier 2 | $164 | $10.85 | **$174.85** | $24.98 | -$2.06 |
| 8 | Tier 2 | $164 | $12.40 | **$176.40** | $22.05 | -$2.06 |
| 9 | Tier 2 | $164 | $13.95 | **$177.95** | $19.77 | -$2.06 |
| 10 | Tier 2 | $164 | $15.50 | **$179.50** | $17.95 | -$2.06 |

#### 成本結構觀察

```
═══════════════════════════════════════════════════════════════
V1 原始 vs V3 優化 — 10 家客戶月成本對比

  GPT-5.1：
    V1：$164 基礎設施 + $207 LLM = $371/月（每家 $37）
    V3：$164 基礎設施 + $100 LLM = $264/月（每家 $26）← 省 29%

  DeepSeek V3.2：
    V1：$164 基礎設施 + $36 LLM = $200/月（每家 $20）
    V3：$164 基礎設施 + $16 LLM = $180/月（每家 $18）← 省 10%

  關鍵發現：
  ⭐ V3 優化讓 GPT-5.1 10 家每家均攤從 $37 降至 $26（-30%）
  ⭐ DeepSeek 因 LLM 單價已極低，優化帶來的絕對金額節省較小
  ⭐ 2→3 家仍是最大成本跳躍點：Tier 1→2 基礎設施 $70→$164（+134%）
  ⭐ V3 推薦配置：精簡 Prompt + top_k=3 + threshold=0.5
═══════════════════════════════════════════════════════════════
```

---

## 6. 向量資料庫策略 — SaaS 擴展規劃

> 所有部署限定在你自己的 GCP 帳號內（asia-east1）。
> 產品從 1 家客戶起步，目標 10 → 100 家。
> 向量資料庫是 SaaS 最容易爆成本的元件，必須提前規劃。

### 6.1 GCP 內向量資料庫選項

```mermaid
graph LR
    subgraph Managed["GCP 託管（免維運）"]
        VS["Vertex AI<br/>Vector Search"]
    end

    subgraph SelfHosted["GCP 自建 Qdrant（需維運）"]
        QVM["GCE VM<br/>單機"]
        QGKE["GKE<br/>StatefulSet"]
    end

    VS -.- |"$68~548+/月<br/>最貴"| cost1["💸"]
    QVM -.- |"$19~40/月<br/>性價比最高"| cost2["🪙"]
    QGKE -.- |"$163+/月<br/>規模化首選"| cost3["💰"]

    style Managed fill:#e8f0fe,stroke:#4285f4
    style SelfHosted fill:#e6f4ea,stroke:#34a853
```

| 方案 | 月成本 | 優點 | 缺點 | 適合階段 |
|------|--------|------|------|---------|
| **Vertex AI Vector Search** | $68~548+ | GCP 原生整合、自動擴展、99.9% SLA、零維運 | **極貴**（最低 $68/月，無 scale-to-zero）；API 與 Qdrant 不同需改 code；vendor lock-in | 200+ 家租戶、不缺預算 |
| **Qdrant on GCE VM** | $19~40 | persistent disk、穩定、**性價比最高**、程式碼零修改 | 單點故障（需自行備份）；手動擴容 | **1~20 家客戶（主力）** |
| **Qdrant on GKE** | $163+ | StatefulSet HA、自動擴展、滾動更新、程式碼零修改 | 基礎費用高（cluster fee）；需 K8s 經驗 | **20~100+ 家客戶** |

### 6.2 GCP 託管選項：Vertex AI Vector Search

定價以 **node-hour** 計費，**永遠在線、無 scale-to-zero**：

| 機型 | 規格 | 每 node-hour | 月成本（24/7） | 來源 |
|------|------|-------------|---------------|------|
| e2-standard-2 | 2 vCPU, 8GB RAM | $0.0938 | **~$68** | [Finout: Vertex AI Pricing 2026](https://www.finout.io/blog/top-16-vertex-services-in-2026) |
| e2-standard-16 | 16 vCPU, 64GB RAM | $0.75 | **~$548** | [Google Dev Forum](https://discuss.google.dev/t/estimating-vertex-ai-vector-search-costs-seeking-cost-effective-alternatives/163824) |
| Storage-Optimized | Capacity Unit | $2.30/hr | **~$1,679** | [Finout: Vertex AI Pricing 2026](https://www.finout.io/blog/top-16-vertex-services-in-2026) |

額外費用：Index 建置 $3.00/GiB、Streaming Update $0.45/GiB

#### 什麼規模才值得用 Vertex AI Vector Search？

```
Vertex AI 最低成本 = $68/月（e2-standard-2，8GB RAM）
自建 Qdrant VM     = $19~40/月（e2-small~e2-medium）
自建 Qdrant GKE    = $163/月（2 replicas HA）

差價 = Vertex AI 省下的「維運人力成本」
```

| 條件 | 自建 Qdrant | Vertex AI Vector Search |
|------|-------------|------------------------|
| 租戶數 | 1~100+ | **200+** |
| 向量總數 | < 10M | **10M+** |
| RAM 需求 | < 8GB（單 VM 可撐） | **8GB+**（需要多節點自動擴展） |
| SLA 要求 | 可接受分鐘級中斷 | **需要 99.9% 可用性保證** |
| 維運團隊 | 有 1 人可處理 VM/K8s | **無 infra 人力，全靠託管** |
| 需改程式碼？ | 不需要（維持 Qdrant SDK） | **需要**（改用 Vertex AI SDK，不同 API） |

> **結論：在你到達 200+ 租戶 / 10M+ 向量 / 需要 99.9% SLA 之前，自建 Qdrant 都是更好的選擇。**
> 即使到了那個規模，GKE 3-node HA（~$250/月）仍然比 Vertex AI（~$548/月）便宜，只是需要維運人力。
> Vertex AI 真正的價值是「用錢換時間」— 當你的 infra 團隊忙不過來時才值得。

### 6.3 向量資料庫記憶體需求估算

Qdrant 的資料主要吃 **RAM**（HNSW 索引）+ **Disk**（原始向量 + payload）：

```
每個向量記憶體 = 維度 × 4 bytes (float32) + metadata overhead
             = 768 × 4 + ~2KB metadata
             ≈ 5 KB/向量

每份文件 ≈ 10~50 個 chunks（向量）
每家客戶 ≈ 100~1,000 份文件
```

| 租戶數 | 文件數 | 向量數（估） | RAM 需求 | Disk 需求 |
|--------|--------|-------------|---------|----------|
| 1 家 | 500 | 10K | ~50 MB | ~100 MB |
| 5 家 | 2,500 | 50K | ~250 MB | ~500 MB |
| 10 家 | 5,000 | 100K | ~500 MB | ~1 GB |
| 20 家 | 10,000 | 200K | ~1 GB | ~2 GB |
| 50 家 | 25,000 | 500K | ~2.5 GB | ~5 GB |
| 100 家 | 50,000 | 1M | ~5 GB | ~10 GB |

### 6.4 GCE VM vs GKE — 深度比較

> 這是你 SaaS 成長過程中最重要的轉換決策。

#### 總覽

| 維度 | GCE VM（單機） | GKE（Kubernetes） |
|------|---------------|-------------------|
| **月成本** | $19~55 | $163+（含 cluster fee） |
| **架構** | 單一 VM + Persistent Disk | StatefulSet + PVC + 多 Pod |
| **高可用（HA）** | ❌ 單點故障 | ✅ 多 replica 自動容錯 |
| **自動擴展** | ❌ 手動 resize VM | ✅ HPA / VPA 自動擴縮 |
| **滾動更新** | ❌ 需停機（或手動 blue-green） | ✅ 零停機滾動更新 |
| **備份** | 手動設定 Snapshot 排程 | 可整合 Velero 自動備份 |
| **監控** | 需手動裝 agent | 內建 GKE monitoring |
| **部署複雜度** | 低（gcloud CLI） | 高（需 K8s manifests） |
| **維運技能** | Linux + Docker 基礎 | K8s 經驗必要 |
| **故障恢復時間** | 分鐘級（手動重啟 / 從 snapshot 恢復） | 秒級（Pod 自動重啟） |
| **資料遷移** | Disk snapshot → 新 VM | PVC 自動掛載 |

#### GCE VM 的優勢場景

```
✅ 租戶數 < 20
✅ 預算有限
✅ 團隊 K8s 經驗不足
✅ 可接受分鐘級故障恢復
✅ 流量穩定、不需頻繁擴縮
```

**VM 維運清單**（你需要自己做的事）：

| 項目 | 頻率 | 做法 |
|------|------|------|
| 自動備份 | 每日 | Snapshot 排程（`gcloud compute disks snapshot`） |
| 系統更新 | 每月 | COS 自動更新，或手動 `apt upgrade` |
| 監控告警 | 持續 | Cloud Monitoring agent + Uptime Check |
| 磁碟擴容 | 按需 | `gcloud compute disks resize`（不停機） |
| VM 升級 | 按需 | 停機 → `gcloud compute instances set-machine-type` → 啟動 |

#### GKE 的優勢場景

```
✅ 租戶數 > 20，且持續成長
✅ 需要 HA（不能因 Qdrant 掛掉而全部停擺）
✅ 流量波動大（尖峰/離峰差異 > 3x）
✅ 團隊有 K8s 經驗
✅ 已有其他服務在 GKE 上（共用 cluster 攤提費用）
```

**GKE 的關鍵成本結構**：

```
GKE cluster fee          = $72/月（有 $74.40 免費額度，幾乎抵銷）
Qdrant Pod 資源費         = vCPU × $0.049/hr + GiB × $0.0054/hr
                          = 依 Pod 規格而定

如果你的 Backend + Frontend 也搬到同一個 GKE cluster：
- cluster fee 共用（不重複收）
- 整體架構統一，維運成本反而可能更低
```

#### 轉換決策樹

```mermaid
graph TD
    Q1{"租戶數 > 20？"}
    Q2{"需要 HA？<br/>（不能接受<br/>分鐘級中斷）"}
    Q3{"團隊有<br/>K8s 經驗？"}
    Q4{"其他服務已在<br/>GKE 上？"}

    VM1["🖥️ GCE VM<br/>（最佳選擇）"]
    VM2["🖥️ GCE VM<br/>+ Snapshot 備份"]
    GKE1["☸️ GKE<br/>（值得投資）"]
    GKE2["☸️ GKE<br/>（共用 cluster 攤提）"]
    LEARN["📚 先學 K8s<br/>或請 SRE"]

    Q1 -->|No| VM1
    Q1 -->|Yes| Q2
    Q2 -->|No| VM2
    Q2 -->|Yes| Q3
    Q3 -->|Yes| Q4
    Q3 -->|No| LEARN
    Q4 -->|Yes| GKE2
    Q4 -->|No| GKE1

    style VM1 fill:#e6f4ea,stroke:#34a853
    style VM2 fill:#e6f4ea,stroke:#34a853
    style GKE1 fill:#e8f0fe,stroke:#4285f4
    style GKE2 fill:#e8f0fe,stroke:#4285f4
    style LEARN fill:#fef7e0,stroke:#fbbc04
```

### 6.5 SaaS 擴展路線圖

```mermaid
graph TD
    subgraph Phase1["Phase 1：Demo + 首家客戶<br/>0~5 家"]
        P1["🖥️ GCE VM (e2-small)<br/>2 GB RAM · 20 GB SSD<br/>~$19/月"]
    end

    subgraph Phase2["Phase 2：成長期<br/>5~20 家"]
        P2["🖥️ GCE VM (e2-medium)<br/>4 GB RAM · 50 GB SSD<br/>~$40/月"]
    end

    subgraph Phase3["Phase 3：規模化<br/>20~100+ 家"]
        P3["☸️ GKE StatefulSet<br/>多節點 · HA · 自動擴展<br/>~$163+/月"]
    end

    P1 -->|"RAM > 80%<br/>（向量 ~40K+）"| P2
    P2 -->|"需要 HA<br/>或 RAM > 4GB"| P3

    style Phase1 fill:#e6f4ea,stroke:#34a853
    style Phase2 fill:#fef7e0,stroke:#fbbc04
    style Phase3 fill:#fce8e6,stroke:#ea4335
```

### 6.6 各階段成本明細

#### Phase 1：GCE VM e2-small（Demo + 首家客戶，0~5 家）

| 項目 | 規格 | 月成本 | 來源 |
|------|------|--------|------|
| VM | e2-small（0.5 vCPU, 2GB RAM） | ~$14.50 | [Economize: e2-small](https://www.economize.cloud/resources/gcp/pricing/compute-engine/e2-small/) |
| SSD | 20 GB Balanced PD | ~$2.20 | [GCP Disk Pricing](https://cloud.google.com/compute/disks-image-pricing) |
| Snapshot 備份 | 20 GB × $0.026 | ~$0.52 | 同上 |
| **合計** | | **~$17.22/月** | |

asia-east1 約 +10%：**~$19/月**

```bash
# 部署指令參考
gcloud compute instances create qdrant-vm \
  --zone=asia-east1-b \
  --machine-type=e2-small \
  --boot-disk-size=20GB \
  --boot-disk-type=pd-balanced \
  --image-family=cos-stable \
  --image-project=cos-cloud \
  --tags=qdrant
```

**轉出信號**：RAM 使用率持續 > 80%（向量 ~40K+），或需要自動備份/HA。

#### Phase 2：GCE VM e2-medium（5~20 家）

| 項目 | 規格 | 月成本 |
|------|------|--------|
| VM | e2-medium（1 vCPU, 4GB RAM） | ~$29 |
| SSD | 50 GB Balanced PD | ~$5.50 |
| Snapshot | 50 GB | ~$1.30 |
| **合計** | | **~$36/月** |

asia-east1：**~$40/月**

**轉出信號**：需要 HA（不能單點故障）、自動擴展、或 RAM > 4GB。

#### Phase 3：GKE StatefulSet（20~100+ 家）

| 項目 | 規格 | 月成本 |
|------|------|--------|
| GKE Autopilot cluster fee | — | ~$0（$74.40 免費額度抵銷） |
| Qdrant Pod（2 vCPU, 8GB） | × 2 replicas | ~$80 |
| PD-SSD（50GB × 2） | | ~$11 |
| **合計** | | **~$91/月**（共用 cluster）<br/>**~$163/月**（獨立 cluster） |

> 如果 Backend + Frontend 也遷到同一 GKE cluster，cluster fee 共用，Qdrant 只需付 Pod 資源費。

參考：[GCP 官方 Qdrant on GKE 教學](https://docs.cloud.google.com/kubernetes-engine/docs/tutorials/deploy-qdrant)

### 6.7 成本對照表 — 按租戶數

| 租戶數 | 向量數 | RAM 需求 | 建議方案 | 月成本 | vs Vertex AI |
|--------|--------|---------|---------|--------|-------------|
| 1 (Demo) | 10K | 50 MB | GCE e2-small | **~$19** | 省 $49 |
| 5 | 50K | 250 MB | GCE e2-small | **~$19** | 省 $49 |
| 10 | 100K | 500 MB | GCE e2-small | **~$19** | 省 $49 |
| 20 | 200K | 1 GB | GCE e2-medium | **~$40** | 省 $28 |
| 50 | 500K | 2.5 GB | GCE e2-medium | **~$40** | 省 $508 |
| 100 | 1M | 5 GB | GKE (2 replicas) | **~$163** | 省 $385 |
| 200+ | 2M+ | 10 GB+ | GKE (3 replicas) 或 Vertex AI | ~$250 / ~$548 | 考慮維運成本取捨 |

> **自建 Qdrant 在 200 家以下都是最佳選擇。**
> 200+ 家時 GKE 3-node HA（~$250/月）仍比 Vertex AI（~$548/月）便宜，差異在維運人力。

---

## 7. 定價參考來源

> 所有定價查詢日期：2026-03-02

### GCP 服務

| 服務 | 參考連結 |
|------|---------|
| Cloud Run | https://cloud.google.com/run/pricing |
| GKE Autopilot | https://cloud.google.com/kubernetes-engine/pricing |
| Cloud SQL for PostgreSQL | https://cloud.google.com/sql/pricing |
| Memorystore for Redis | https://cloud.google.com/memorystore/docs/redis/pricing |
| Cloud CDN | https://cloud.google.com/cdn/pricing |
| Cloud Load Balancing | https://cloud.google.com/load-balancing/pricing |
| Cloud Domains | https://cloud.google.com/domains/pricing |
| Artifact Registry | https://cloud.google.com/artifact-registry/pricing |
| Cloud Armor (WAF) | https://cloud.google.com/armor/pricing |
| VPC Network / Egress | https://cloud.google.com/vpc/network-pricing |
| Secret Manager | https://cloud.google.com/security/products/secret-manager#pricing |

### 向量資料庫

| 服務 | 參考連結 |
|------|---------|
| Vertex AI Vector Search Pricing | https://cloud.google.com/vertex-ai/pricing |
| Vertex AI Vector Search 定價分析 | https://www.finout.io/blog/top-16-vertex-services-in-2026 |
| Vertex AI 社群成本討論 | https://discuss.google.dev/t/estimating-vertex-ai-vector-search-costs-seeking-cost-effective-alternatives/163824 |
| Qdrant on GKE 官方教學 | https://docs.cloud.google.com/kubernetes-engine/docs/tutorials/deploy-qdrant |
| GCE VM Pricing (e2-small) | https://www.economize.cloud/resources/gcp/pricing/compute-engine/e2-small/ |
| GCE VM Pricing (e2-medium) | https://www.economize.cloud/resources/gcp/pricing/compute-engine/e2-medium/ |
| GCE Disk Pricing | https://cloud.google.com/compute/disks-image-pricing |

### AI 模型 API

| 服務 | 參考連結 |
|------|---------|
| OpenAI API Pricing | https://openai.com/api/pricing/ |
| Anthropic Claude Pricing | https://docs.anthropic.com/en/docs/about-claude/pricing |
| DeepSeek API Pricing | https://api-docs.deepseek.com/quick_start/pricing |
| Google Gemini API Pricing | https://ai.google.dev/pricing |

### 外部平台（方案 C）

| 服務 | 參考連結 |
|------|---------|
| Render Pricing | https://render.com/pricing |
| Neon Pricing | https://neon.tech/pricing |
| Cloudflare Pages | https://pages.cloudflare.com |

### 工具

| 用途 | 工具 |
|------|------|
| GCP 官方成本估算器 | https://cloud.google.com/products/calculator |
| OpenAI Token 計算器 | https://platform.openai.com/tokenizer |
| Qdrant Cluster Calculator | https://gpuvec.com/tools/qdrant-calculator |

---

## 附錄 A：Token 實測紀錄

### 三組配置實測對照（2026-03-05）

> **測試環境**：Cloud Run asia-east1 → DeepSeek API（deepseek-chat）
> **Embedding**：text-embedding-3-small
> **測試情境**：電商客服 RAG 問答（退貨政策、產品說明等），每組 3 輪對話

#### 實測 #1：V1 原始配置

```
System Prompt：完整版（~800 tokens）
RAG 參數：top_k=5, score_threshold=0.3
測試時間：10:18

| 輪次 | Input Tokens | Output Tokens |
|------|-------------|---------------|
| 第 1 輪 | 3,665 | 228 |
| 第 2 輪 | 4,120 | 169 |
| 第 3 輪 | 4,230 | 169 |
| **3 輪合計** | **12,015** | **566** |
```

#### 實測 #2：V2 精簡 Prompt

```
System Prompt：精簡版（~400 tokens）— 砍掉資料性內容，交給 RAG
RAG 參數：top_k=5, score_threshold=0.3（與 V1 相同）
測試時間：10:48

| 輪次 | Input Tokens | Output Tokens |
|------|-------------|---------------|
| 第 1 輪 | 2,878 | 215 |
| 第 2 輪 | 3,217 | 178 |
| 第 3 輪 | 3,468 | 179 |
| **3 輪合計** | **9,563** | **572** |
```

#### 實測 #3：V3 全面優化

```
System Prompt：精簡版（~400 tokens）
RAG 參數：top_k=3, score_threshold=0.5（減少檢索量 + 提高品質門檻）
測試時間：11:03

| 輪次 | Input Tokens | Output Tokens |
|------|-------------|---------------|
| 第 1 輪 | 1,438 | 154 |
| 第 2 輪 | 1,672 | 118 |
| 第 3 輪 | 1,821 | 112 |
| **3 輪合計** | **4,931** | **384** |
```

### 三組配置綜合比較

#### Token 消耗對比

| 配置 | System Prompt | top_k | threshold | Input | Output | **Total** | **vs V1** |
|------|-------------|-------|-----------|-------|--------|-----------|-----------|
| **V1 原始** | 完整版 ~800 tok | 5 | 0.3 | 12,015 | 566 | **12,581** | — |
| **V2 精簡 Prompt** | 精簡版 ~400 tok | 5 | 0.3 | 9,563 | 572 | **10,135** | **-19%** |
| **V3 全面優化** | 精簡版 ~400 tok | 3 | 0.5 | 4,931 | 384 | **5,315** | **-58%** |

#### 優化因子拆解

| 優化手段 | 影響範圍 | Token 節省 | 說明 |
|---------|---------|-----------|------|
| Prompt 精簡（V1→V2） | System Prompt 部分 | **-19%** | 砍掉資料性內容（講師名、分類），交給 RAG |
| RAG 參數調整（V2→V3） | RAG Context 部分 | **-48%** | top_k 5→3 減少檢索量 + threshold 0.3→0.5 過濾低分 |
| **合計（V1→V3）** | **全部** | **-58%** | 兩項疊加效果 |

> **關鍵發現**：RAG 參數優化（top_k + threshold）的影響遠大於 Prompt 精簡。
> Token 結構中 RAG Context 佔 60-70%，是最大的優化槓桿。

#### 每租戶月 LLM 成本對比（GPT-5.1, 1,000 次對話/月）

| 配置 | Input Token/月 | Input 成本 | Output 成本 | Embed | **月 LLM 費** | **vs V1** |
|------|---------------|-----------|------------|-------|-------------|-----------|
| V1 原始 | 12.015M | $15.02 | $5.66 | $0.01 | **$20.69** | — |
| V2 精簡 Prompt | 9.563M | $11.95 | $5.72 | $0.01 | **$17.68** | -$3.01（-15%） |
| V3 全面優化 | 4.931M | $6.16 | $3.84 | $0.01 | **$10.01** | -$10.68（-52%） |

#### 每租戶月 LLM 成本對比（DeepSeek V3.2, 1,000 次對話/月）

| 配置 | Input Token/月 | Input 成本 | Output 成本 | Embed | **月 LLM 費** | **vs V1** |
|------|---------------|-----------|------------|-------|-------------|-----------|
| V1 原始 | 12.015M | $3.36 | $0.24 | $0.01 | **$3.61** | — |
| V2 精簡 Prompt | 9.563M | $2.68 | $0.24 | $0.01 | **$2.93** | -$0.68（-19%） |
| V3 全面優化 | 4.931M | $1.38 | $0.16 | $0.01 | **$1.55** | -$2.06（-57%） |

#### 10 家客戶年度成本對比

| 配置 | GPT-5.1 月 LLM（10 家） | GPT-5.1 年 LLM | DeepSeek 月 LLM（10 家） | DeepSeek 年 LLM |
|------|------------------------|----------------|-------------------------|----------------|
| V1 原始 | $206.90 | $2,482.80 | $36.10 | $433.20 |
| V2 精簡 Prompt | $176.80 | $2,121.60 | $29.30 | $351.60 |
| V3 全面優化 | $100.10 | $1,201.20 | $15.50 | $186.00 |
| **V1→V3 年省** | | **$1,281.60** | | **$247.20** |

> **結論**：
> 1. **V3 全面優化是推薦配置** — Token 減少 58%，GPT-5.1 年省 $1,282（10 家客戶）
> 2. **RAG 參數是主要槓桿** — top_k 5→3 + threshold 0.3→0.5，貢獻了 -48% 的 Token 節省
> 3. **Prompt 精簡是加分項** — 年省 ~$361（GPT-5.1, 10 家），但更重要的是架構合理性：資料歸 RAG，行為歸 Prompt

### 實測模板（空白）

```
測試日期：____
測試情境：____
LLM 模型：____
Embedding 模型：____
RAG 參數：top_k=___, score_threshold=___

| 輪次 | Input Tokens | Output Tokens | Embedding Tokens |
|------|-------------|---------------|-----------------|
| 第 1 輪 | | | |
| 第 2 輪 | | | |
| 第 3 輪 | | | |
| **合計** | T_in = | T_out = | T_emb = |
```

## 附錄 B：敏感度分析

LLM 成本佔比高時，模型選擇影響巨大。以下以**方案 C（最低成本）**為基底，搭配不同模型 × 不同流量的成本矩陣。

> **假設基礎**：V1 原始（12,015 in / 566 out）vs V3 優化（4,931 in / 384 out）
> **流量模型**：10,000 訪客/租戶/月 × 10% 使用率 = 1,000 對話/月

### 月度成本 — V1 原始配置 × 方案 C（$45/月）

> 以「租戶數 × 1,000 對話/租戶」計算月 LLM 成本

| 租戶數（月對話數） | GPT-5 Nano | DeepSeek V3.2 | GPT-5.1 | Claude Sonnet 4.6 |
|-----------------|------------|---------------|---------|-------------------|
| 1 家（1K） | $45 + $0.84 = **$45.84** | $45 + $3.61 = **$48.61** | $45 + $20.69 = **$65.69** | $45 + $44.55 = **$89.55** |
| 3 家（3K） | $45 + $2.52 = **$47.52** | $45 + $10.83 = **$55.83** | $45 + $62.07 = **$107.07** | $45 + $133.65 = **$178.65** |
| 5 家（5K） | $45 + $4.20 = **$49.20** | $45 + $18.05 = **$63.05** | $45 + $103.45 = **$148.45** | $45 + $222.75 = **$267.75** |
| 10 家（10K） | $45 + $8.40 = **$53.40** | $45 + $36.10 = **$81.10** | $45 + $206.90 = **$251.90** | $45 + $445.50 = **$490.50** |

### 月度成本 — V3 全面優化 × 方案 C（$45/月）⭐ 推薦

| 租戶數（月對話數） | GPT-5 Nano | DeepSeek V3.2 | GPT-5.1 | Claude Sonnet 4.6 |
|-----------------|------------|---------------|---------|-------------------|
| 1 家（1K） | $45 + $0.41 = **$45.41** | $45 + $1.55 = **$46.55** | $45 + $10.01 = **$55.01** | $45 + $20.56 = **$65.56** |
| 3 家（3K） | $45 + $1.23 = **$46.23** | $45 + $4.65 = **$49.65** | $45 + $30.03 = **$75.03** | $45 + $61.68 = **$106.68** |
| 5 家（5K） | $45 + $2.05 = **$47.05** | $45 + $7.75 = **$52.75** | $45 + $50.05 = **$95.05** | $45 + $102.80 = **$147.80** |
| 10 家（10K） | $45 + $4.10 = **$49.10** | $45 + $15.50 = **$60.50** | $45 + $100.10 = **$145.10** | $45 + $205.60 = **$250.60** |

> **觀察**：
> - V3 優化後，GPT-5.1 10 家從 $252 降至 $145（**-42%**），成本與 V1 DeepSeek 接近
> - V3 + DeepSeek 10 家僅 $60.50，LLM 只佔 26%，基礎設施為主要成本
> - V3 讓 Claude Sonnet 4.6 的 10 家成本從 $491 降至 $251 — 原本不可行的模型變得可考慮

---

## 附錄 C：部署前置作業 Checklist

> 在部署任何方案前，確認以下項目已完成。

- [ ] Backend Dockerfile 建置並測試通過
- [ ] CORS `allow_origins` 改為環境變數（現硬編碼 `localhost:3000`）
- [ ] `.env.example` 更新 `VITE_API_URL` 指向正式 Backend URL
- [ ] 確認公司資安政策：DB data 可否放外部平台（決定方案 C vs C-GCP 混合）
- [ ] Qdrant GCE VM 部署腳本準備（所有方案共用）
- [ ] LLM API Key 透過 Secret Manager / 環境變數管理（禁止硬編碼）

---

## 附錄 D：自建 vs 外部方案成本對照（18M Token 基準）

> **對照對象**：某外部 AI 客服方案，報價 **18M tokens / 50,000 TWD**
> **匯率**：1 USD = 32.2 TWD
> **目的**：以相同 Token 消耗量（18M）為基準，比較自建方案的成本優勢

### Token 結構（自建方案實測 — 三組配置）

> 自建方案每次對話的 token 分佈（2026-03-05 實測 3 輪）

| 成分 | V1 原始 | V2 精簡 Prompt | V3 全面優化 |
|------|--------|---------------|------------|
| LLM Input | 12,015 | 9,563 | 4,931 |
| LLM Output | 566 | 572 | 384 |
| Embedding | 300 | 300 | 300 |
| **每次對話合計** | **12,881** | **10,435** | **5,615** |
| Input 佔比 | 93.3% | 91.6% | 87.8% |

### 18M Token 可服務量（三組配置對比）

| | V1 原始 | V2 精簡 Prompt | V3 全面優化 |
|--|--------|---------------|------------|
| 每次對話 token | 12,881 | 10,435 | 5,615 |
| **18M 可服務對話數** | **1,397 次** | **1,725 次** | **3,206 次** |
| 等同月數（1,000 次/月） | 1.40 個月 | 1.73 個月 | **3.21 個月** |
| **vs V1** | — | **+23%** | **+129%** |

> **V3 全面優化讓相同 18M token 預算從 1,397 次對話提升到 3,206 次 — 服務量翻倍**

### 成本對照：同樣消耗 18M Token

#### 純 LLM API 成本（變動成本）

> 不同配置下 18M token 的 input/output 比例不同，因此 LLM 費用略有差異

| 方案 | 18M Token 費用 | 每百萬 Token 單價 |
|------|--------------|-----------------|
| **外部方案** | **50,000 TWD** | **2,778 TWD/M** |
| 自建 GPT-5.1（V1） | 931 TWD ($28.92) | 51.7 TWD/M |
| 自建 GPT-5.1（V3） | 1,033 TWD ($32.08) | 57.4 TWD/M |
| 自建 DeepSeek V3.2 | 160 TWD ($4.97) | 8.9 TWD/M |
| 自建 GPT-5 Nano | 42 TWD ($1.30) | 2.3 TWD/M |

> 純 LLM API 成本：**自建比外部方案便宜 48～1,190 倍**

#### 含基礎設施的總成本（18M Token 期間）

> 自建方案需加上 GCP 基礎設施費用（Tier 1: $70/月）
> V3 因每對話 token 更少，18M token 跨越更多月份（3.21 月），基礎設施費用因此更高
> **但 V3 服務了 3,206 次對話（V1 僅 1,397 次）— 單次對話成本大幅降低**

| 方案 | LLM 費 | 基礎設施 | **18M Token 總成本** | 服務對話數 | **每次對話成本** |
|------|-------|---------|---------------------|----------|--------------|
| **外部方案** | 50,000 TWD | 含在內 | **50,000 TWD** | 依方案 | **35.8 TWD** ⚠️ |
| 自建 V1 GPT-5.1 | 931 | 3,156（1.4 月） | **4,087 TWD** | 1,397 | **2.93 TWD** |
| 自建 V3 GPT-5.1 | 1,033 | 7,233（3.21 月） | **8,266 TWD** | 3,206 | **2.58 TWD** |
| 自建 V1 DeepSeek | 160 | 3,156（1.4 月） | **3,316 TWD** | 1,397 | **2.37 TWD** |
| 自建 V3 DeepSeek | 160 | 7,233（3.21 月） | **7,393 TWD** | 3,206 | **2.31 TWD** |

> **注意**：外部方案的 35.8 TWD/次 已含基礎設施；自建方案 2.3-2.9 TWD/次 也已含基礎設施。

### 三組配置成本差異（以 18M Token 為基準）

| | V1 原始 | V2 精簡 Prompt | V3 全面優化 |
|--|--------|---------------|------------|
| 18M 可服務對話數 | 1,397 | 1,725 | **3,206** |
| 服務月數 | 1.40 月 | 1.73 月 | **3.21 月** |
| vs V1 服務量 | — | +23% | **+129%** |
| GPT-5.1 每次對話成本 | 2.93 TWD | 2.56 TWD | **2.58 TWD** |

> **V3 的核心價值：同樣 18M token 預算，服務量翻倍（1,397→3,206 次）**

### 月度成本對照（每租戶 1,000 次對話）

| 方案 | 月 Token 消耗 | 月成本 | 年成本 |
|------|-------------|--------|--------|
| **外部方案**（按比例） | — | ~35,833 TWD | ~430,000 TWD |
| 自建 V1 GPT-5.1 + 基礎設施 | 12.9M | ~2,912 TWD ($90.4) | ~34,944 TWD |
| 自建 V3 GPT-5.1 + 基礎設施 | 5.6M | ~2,578 TWD ($80.0) | ~30,936 TWD |
| 自建 V1 DeepSeek + 基礎設施 | 12.9M | ~2,370 TWD ($73.6) | ~28,440 TWD |
| 自建 V3 DeepSeek + 基礎設施 | 5.6M | ~2,306 TWD ($71.6) | ~27,672 TWD |

> **外部方案月費按比例換算**：50,000 TWD ÷ 1.40 月 = ~35,714 TWD/月

### 50,000 TWD 預算對標：全 HA × 不同使用率 × 定價策略

> **比較基準**：外部方案 50,000 TWD / 18M tokens vs 自建方案 V3 全面優化
> **自建方案一律含全 HA**（Cloud SQL HA + Qdrant GKE 2-replica），從第一家客戶即正式規格
> **匯率**：1 USD = 32.2 TWD

#### 基礎設施成本（全 HA）

> 參考 §5.8 HA 附加費：Cloud SQL HA = 2× SQL 費用，Qdrant GKE = VM→GKE 差價

| Tier | 租戶數 | 無 HA | Cloud SQL HA | Qdrant GKE | **含 HA 月費** | **TWD** |
|------|-------|-------|-------------|-----------|-------------|---------|
| Tier 2 | 1-10 家 | $164 | +$100 | +$72 | **$336/月** | **10,819** |
| Tier 3 | 10-30 家 | $277 | +$180 | +$96 | **$553/月** | **17,807** |

#### 外部方案：50,000 TWD 可服務家數

| 使用率 | 對話/租戶/月 | Token/租戶/月（V3） | **18M 可服務家數** | **每家分攤售價** |
|-------|-----------|-------------------|-----------------|--------------|
| 10% | 1,000 | 5.615M | **3 家** | **16,667 TWD** |
| 5% | 500 | 2.808M | **6 家** | **8,333 TWD** |
| 3% | 300 | 1.685M | **10 家** | **5,000 TWD** |
| 1% | 100 | 0.562M | **32 家** | **1,563 TWD** |

#### 自建方案（全 HA）：同家數的實際成本

> 18M token 總工作量固定 → LLM 成本恆定（GPT-5.1 ~967 TWD）
> 差異只在基礎設施 Tier：1-10 家 = Tier 2 HA（10,819 TWD），10+ 家 = Tier 3 HA（17,807 TWD）

| 使用率 | 家數 | Tier | 基礎設施（HA） | LLM（GPT-5.1） | **總成本** | **每家不賠本價** | vs 外部售價 |
|-------|------|------|-------------|-------------|----------|-------------|----------|
| 10% | 3 | Tier 2 HA | 10,819 | 967 | **11,786** | **3,929 TWD** | 外部貴 4.2 倍 |
| 5% | 6 | Tier 2 HA | 10,819 | 967 | **11,786** | **1,964 TWD** | 外部貴 4.2 倍 |
| 3% | 10 | Tier 2 HA | 10,819 | 967 | **11,786** | **1,179 TWD** | 外部貴 4.2 倍 |
| 1% | 32 | Tier 3 HA | 17,807 | 1,031 | **18,838** | **589 TWD** | 外部貴 2.7 倍 |

#### 定價策略比較：雙方不賠本底線（全 HA，GPT-5.1）

```
═══════════════════════════════════════════════════════════════
  每家每月不賠本底價（TWD）— 自建全 HA + GPT-5.1

  使用率        外部方案    自建(GPT-5.1)   價差倍數
  ─────────────────────────────────────────────────────
  10%（3家）    16,667       3,929          4.2x
   5%（6家）     8,333       1,964          4.2x
   3%（10家）    5,000       1,179          4.2x
   1%（32家）    1,563         589          2.7x

  → 即使含全 HA + GPT-5.1（最貴模型），不賠本價仍為外部方案的 1/3 ~ 1/4
  → 最保守的 1% 場景下，仍有 2.7 倍價差優勢
═══════════════════════════════════════════════════════════════
```

#### 定價策略模擬：自建方案收半價（全 HA，GPT-5.1）

> 定價為外部方案的 **50%**，含全 HA + GPT-5.1 的收入與利潤：

| 使用率 | 家數 | 外部售價/家 | 自建半價/家 | **月收入** | **月成本** | **月淨利** | **毛利率** |
|-------|------|-----------|-----------|---------|----------|---------|---------|
| 10% | 3 | 16,667 | 8,333 | 25,000 | 11,786 | **13,214** | **53%** |
| 5% | 6 | 8,333 | 4,167 | 25,002 | 11,786 | **13,216** | **53%** |
| 3% | 10 | 5,000 | 2,500 | 25,000 | 11,786 | **13,214** | **53%** |
| 1% | 32 | 1,563 | 782 | 25,024 | 18,838 | **6,186** | **25%** |

> **全 HA + GPT-5.1（最保守估算）、收半價，仍有 25-53% 毛利率。**

#### 定價策略模擬：自建方案收三折（全 HA，GPT-5.1）

| 使用率 | 家數 | 外部售價/家 | 自建三折/家 | **月收入** | **月成本** | **月淨利** | **毛利率** |
|-------|------|-----------|-----------|---------|----------|---------|---------|
| 10% | 3 | 16,667 | 5,000 | 15,000 | 11,786 | **3,214** | **21%** |
| 5% | 6 | 8,333 | 2,500 | 15,000 | 11,786 | **3,214** | **21%** |
| 3% | 10 | 5,000 | 1,500 | 15,000 | 11,786 | **3,214** | **21%** |
| 1% | 32 | 1,563 | 469 | 15,008 | 18,838 | **-3,830** | **-26%** ⚠️ |

> **三折 + 1% 使用率 = 虧損**。此場景自建方案的價格底線為外部方案的 **38%**（589 TWD/家）。

#### 成本結構視覺化（月費對比，全 HA + GPT-5.1，單位：TWD）

```
使用率 10%（3 家，全 HA + GPT-5.1）
  外部方案   ██████████████████████████████████████████████████ 50,000
  自建成本   ███████████                                       11,786
  自建半價收 █████████████████████████                         25,000  ← 客戶省50%, 我方賺53%

使用率 5%（6 家，全 HA + GPT-5.1）
  外部方案   ██████████████████████████████████████████████████ 50,000
  自建成本   ███████████                                       11,786
  自建半價收 █████████████████████████                         25,000

使用率 3%（10 家，全 HA + GPT-5.1）
  外部方案   ██████████████████████████████████████████████████ 50,000
  自建成本   ███████████                                       11,786
  自建半價收 █████████████████████████                         25,000

使用率 1%（32 家，全 HA + GPT-5.1）
  外部方案   ██████████████████████████████████████████████████ 50,000
  自建成本   ██████████████████                                18,838
  自建半價收 █████████████████████████                         25,024  ← 毛利率 25%
```

### 方案總比較：各情境成本與定價矩陣

> 以下為完整的情境比較總表。
> 所有自建方案均含**全 HA + GPT-5.1**（最保守估算），V3 全面優化配置。

#### 每家每月不賠本底價一覽（TWD）

| 使用率 | 家數 | 外部方案 | 自建 GPT-5.1（全 HA） | **價差倍數** |
|-------|------|---------|---------------------|-----------|
| 10% | 3 | 16,667 | 3,929 | **4.2x** |
| 5% | 6 | 8,333 | 1,964 | **4.2x** |
| 3% | 10 | 5,000 | 1,179 | **4.2x** |
| 1% | 32 | 1,563 | 589 | **2.7x** |

#### 各定價策略下的月毛利率（GPT-5.1，全 HA）

| 使用率 | 家數 | 月成本 | 收原價(100%) | **收半價(50%)** | 收三折(30%) | 不賠本底線 |
|-------|------|-------|-----------|-------------|-----------|----------|
| 10% | 3 | 11,786 | 76% | **53%** | 21% | 24% |
| 5% | 6 | 11,786 | 76% | **53%** | 21% | 24% |
| 3% | 10 | 11,786 | 76% | **53%** | 21% | 24% |
| 1% | 32 | 18,838 | 62% | **25%** | -26% ⚠️ | 38% |

> **建議定價帶：外部方案的 40-50%** — 毛利率 25-53%，客戶感受划算，自建方案穩定獲利

#### 年度損益預估（GPT-5.1，全 HA，收半價）

| 使用率 | 家數 | 月收入 | 月成本 | **月淨利** | **年淨利** |
|-------|------|-------|-------|---------|---------|
| 10% | 3 | 25,000 | 11,786 | 13,214 | **158,568 TWD** |
| 5% | 6 | 25,002 | 11,786 | 13,216 | **158,592 TWD** |
| 3% | 10 | 25,000 | 11,786 | 13,214 | **158,568 TWD** |
| 1% | 32 | 25,024 | 18,838 | 6,186 | **74,232 TWD** |

> 若改用 DeepSeek V3.2（LLM 成本降 85%），年淨利再增加 ~10,000 TWD。

#### 結論

> 1. **全 HA + GPT-5.1（最保守估算）仍有明顯優勢**：不賠本底價僅外部方案的 24-38%
> 2. **推薦定價帶 = 外部方案的 40-50%**：
>    - 客戶端：比外部方案便宜一半以上
>    - 營運端：含全 HA + GPT-5.1 仍有 25-53% 毛利率
> 3. **1% 使用率是唯一風險區**：三折以下會虧損，底線在外部方案的 38%（589 TWD/家）
> 4. **實務判斷**：每天 3.3 次對話（1% 使用率）的客戶通常不會購買付費 AI 客服方案，正式營運客戶預期在 3-10%
> 5. **風險提醒**：
>    - 上表毛利率未扣除開發人力（一次性）和維運人力（持續），需依團隊規模另行評估
>    - 外部方案 50,000 TWD 為全包價（含開發 + 維運 + 技術支援）
