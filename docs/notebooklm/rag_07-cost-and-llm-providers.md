# 測試機環境成本 + LLM 供應商選型

> 更新日期：2026-03-16
> 定價基準：GCP asia-east1（台灣彰化）、各廠商官方 API 定價
> 匯率：1 USD = 32.2 TWD

---

## 一、GCP 基礎設施：兩方案比較

### 共用元件（兩方案相同）

| 服務 | GCP 產品 | 規格 | 月費 | 備註 |
|------|---------|------|------|------|
| Backend API | Cloud Run | 1 vCPU, 1 GiB, min instances: 0 | ~$0-15 | 按用量，idle 趨近 $0 |
| PostgreSQL + pgvector | Cloud SQL | db-custom-1-3840（1 vCPU, 3.75GB）, 20GB SSD | ~$50 | 含向量搜尋 + 自動備份 7 天 |
| Redis | Memorystore Basic | 1 GB | ~$35 | Session / cache / rate limit / 通知節流 |
| VPC Connector | Serverless VPC Access | — | ~$7 | Cloud Run → Cloud SQL / Redis 必要 |
| Container Registry | Artifact Registry | — | ~$1 | Docker image 儲存 |
| Logging | Cloud Logging + Monitoring | — | ~$0-5 | 免費額度通常夠 |
| Secret Manager | Secret Manager | 5-10 secrets | ~$0.5 | API keys 加密存放 |
| **共用小計** | | | **~$93-113** | |

---

### 方案 A：Firebase Hosting（推薦）

| 項目 | 說明 | 月費 |
|------|------|------|
| 共用基礎設施 | Cloud Run + Cloud SQL + Redis + 其他 | ~$93-113 |
| **Firebase Hosting** | 前端 SPA + widget.js，內建全球 CDN + 自動 TLS + 自訂域名 | **$0-5** |
| | | |
| **方案 A 合計** | | **~$93-118/月** |
| | | **~3,000-3,800 TWD/月** |

Firebase Hosting 免費額度：

| 項目 | 免費額度 | 超出費率 |
|------|---------|---------|
| 儲存 | 10 GB | $0.026/GB |
| 流量 | 360 MB/天（~10 GB/月） | $0.15/GB |
| 自訂域名 | 不限 | — |
| SSL | 自動 Google-managed | — |

> Firebase 是 Google 旗下產品，用同一個 GCP Project 啟用，帳單合併在 GCP billing。

---

### 方案 B：GCS + Cloud CDN + External Load Balancer

| 項目 | 說明 | 月費 |
|------|------|------|
| 共用基礎設施 | Cloud Run + Cloud SQL + Redis + 其他 | ~$93-113 |
| GCS Bucket | 前端靜態檔儲存（Standard, asia-east1） | ~$0.02-1 |
| **External HTTPS Load Balancer** | **5 條轉發規則（固定費）+ 流量費** | **~$18-20** |
| Cloud CDN | 快取命中流量（$0.02-0.08/GB 依地區） | ~$1-5 |
| Google-managed SSL | 需掛在 LB 上 | $0 |
| Static IP | LB 使用中免費 | ~$0 |
| | | |
| **方案 B 合計** | | **~$113-142/月** |
| | | **~3,600-4,600 TWD/月** |

方案 B 需要設定的元件：

```
GCS Bucket → Cloud CDN → External HTTPS Load Balancer → 自訂域名
                                    ↓
                              Cloud Run（API proxy）
```

> 這些 infra 都可以幫忙設定，寫成 Terraform 或 gcloud CLI script 一次部署完。

---

### 方案 A vs B 總結

| 維度 | 方案 A（Firebase Hosting） | 方案 B（GCS + CDN + LB） |
|------|--------------------------|--------------------------|
| **月費** | **~$93-118** | ~$113-142 |
| **年差** | — | **+$240-300/年** |
| CDN | ✅ 內建 | ✅ Cloud CDN |
| 自訂域名 + TLS | ✅ 自動 | ✅ 需手動（LB + cert） |
| 初始設定 | 5 分鐘 | 2-4 小時（10 步驟） |
| 維運 | 零 | LB + CDN 需監控 |
| 適合規模 | 1-50 家客戶 | 50+ 家 / 特殊 CDN 需求 |
| **建議** | **✅ 現階段選這個** | 規模化後再考慮 |

---

## 二、LLM 供應商 + 模型清單

> 定價截止日：2026-03-16，來源：各廠商官方 API 定價頁面

### OpenAI

| 模型 | Input $/M | Output $/M | Context | Tool Use | ReAct 適用 | 推薦 |
|------|----------|-----------|---------|----------|-----------|------|
| **GPT-5.2** | $1.75 | $14.00 | 128K | ⭐⭐⭐ | ✅ 旗艦推理 | 🏆 最強品質 |
| **GPT-5.1** | $1.25 | $10.00 | 128K | ⭐⭐⭐ | ✅ 主力推薦 | |
| **GPT-5 mini** | $0.25 | $2.00 | 128K | ⭐⭐ | ✅ CP 值之王 | 💰 最佳 CP |
| **GPT-5 nano** | $0.05 | $0.40 | 128K | ⭐ | ⚠️ 僅路由/分類 | |
| GPT-4o-mini | $0.15 | $0.60 | 128K | ⭐⭐ | ⚠️ 舊款但穩定 | |

### Anthropic（Claude）

| 模型 | Input $/M | Output $/M | Context | Tool Use | ReAct 適用 | 推薦 |
|------|----------|-----------|---------|----------|-----------|------|
| **Claude Opus 4.6** | $5.00 | $25.00 | 1M | ⭐⭐⭐ | ✅ 最強推理 | |
| **Claude Sonnet 4.6** | $3.00 | $15.00 | 1M | ⭐⭐⭐ | ✅ 品質 ≈ Opus 85% | 🏆 最強 Tool Use |
| **Claude Haiku 4.5** | $1.00 | $5.00 | 200K | ⭐⭐ | ✅ 輕量 ReAct | 💰 最佳 CP |

### Google（Gemini）

| 模型 | Input $/M | Output $/M | Context | Tool Use | ReAct 適用 | 推薦 |
|------|----------|-----------|---------|----------|-----------|------|
| **Gemini 3.1 Pro** | $2.00 | $12.00 | 1M | ⭐⭐⭐ | ✅ Benchmark #1 | 🏆 最強品質 |
| **Gemini 3 Flash** | $0.50 | $3.00 | 1M | ⭐⭐ | ✅ 旗艦 80% 品質 | 💰 最佳 CP |
| **Gemini 2.5 Flash** | $0.30 | $2.50 | 1M | ⭐⭐ | ✅ 穩定可靠 | |
| **Gemini 2.5 Flash-Lite** | $0.10 | $0.40 | 1M | ⭐ | ⚠️ 僅路由/分類 | |
| ~~Gemini 2.0 Flash-Lite~~ | ~~$0.075~~ | ~~$0.30~~ | ~~1M~~ | — | ❌ | ⚠️ 2026/06/01 停用 |

### Embedding 模型

| 模型 | 廠商 | $/M tokens | 維度 | 推薦 |
|------|------|-----------|------|------|
| **text-embedding-3-small** | OpenAI | $0.02 | 1536 | 💰 最便宜，品質足夠 |
| text-embedding-3-large | OpenAI | $0.13 | 3072 | 高精度需求 |
| Gemini Embedding 2 | Google | $0.20 | 3072 | 多模態需求 |
| Voyage 3.5 | Voyage AI | $0.06 | 1024 | 免費額度 200M tokens |

---

## 三、ReAct Agent 推薦組合

> ReAct Agent 需要強 Tool Use / Function Calling 能力，不是所有模型都適合。

### Tool Use 能力排名（2026/03 實測）

```
最強：Claude Sonnet 4.6 ≈ GPT-5.2 > Gemini 3.1 Pro > GPT-5.1
高 CP：GPT-5 mini > Gemini 3 Flash > Claude Haiku 4.5
低成本：GPT-5 nano > GPT-4o-mini（其餘不建議用於 tool use）
```

### 推薦組合 1：🏆 最強品質

| 用途 | 模型 | 月費（低用量） | 說明 |
|------|------|-------------|------|
| ReAct 推理 + Tool Use | **Claude Sonnet 4.6** | ~$2-10 | Tool Use 業界最強 |
| 路由 / 分類 | GPT-5 nano | ~$0.01-0.05 | 低成本簡單判斷 |
| Embedding | text-embedding-3-small | ~$0.02-0.1 | 最便宜 |
| **API 月費小計** | | **~$2-10** | |

> 適合：高品質需求、客戶要求最佳體驗、複雜多步推理場景

### 推薦組合 2：💰 最佳 CP 值（推薦）

| 用途 | 模型 | 月費（低用量） | 說明 |
|------|------|-------------|------|
| ReAct 推理 + Tool Use | **GPT-5 mini** | ~$0.2-1 | CP 值最高，Tool Use 能力夠用 |
| 路由 / 分類 | GPT-5 nano | ~$0.01-0.05 | 同上 |
| Embedding | text-embedding-3-small | ~$0.02-0.1 | 同上 |
| **API 月費小計** | | **~$0.2-1.2** | |

> 適合：一般企業客服、品質與成本平衡、初期上線推薦

### 推薦組合 3：🔥 極致省錢

| 用途 | 模型 | 月費（低用量） | 說明 |
|------|------|-------------|------|
| ReAct 推理 + Tool Use | **Gemini 3 Flash** | ~$0.1-0.5 | 1M context + 低價 |
| 路由 / 分類 | Gemini 2.5 Flash-Lite | ~$0.01-0.03 | 超低成本 |
| Embedding | text-embedding-3-small | ~$0.02-0.1 | 同上 |
| **API 月費小計** | | **~$0.1-0.6** | |

> 適合：預算極度有限、簡單客服場景、大量呼叫需壓低成本

---

## 四、供應商綁定 vs 混合使用

### 選項 A：綁定單一供應商

| 供應商 | ReAct 推理 | 路由 | Embedding | 月 API 費 | 優缺點 |
|--------|----------|------|-----------|----------|--------|
| **全 OpenAI** | GPT-5 mini | GPT-5 nano | text-embedding-3-small | ~$0.2-1.2 | ✅ 一張帳單 / ⚠️ 單點風險 |
| **全 Google** | Gemini 3 Flash | Gemini 2.5 Flash-Lite | Gemini Embedding 2 | ~$0.1-0.8 | ✅ 最便宜 / ⚠️ Tool Use 稍弱 |
| **全 Anthropic** | Claude Sonnet 4.6 | Claude Haiku 4.5 | （無 Embedding）需搭 OpenAI | ~$2-10 | ✅ 品質最高 / ❌ 無 Embedding |

### 選項 B：混合使用（推薦）

| 用途 | 推薦模型 | 供應商 | 理由 |
|------|---------|--------|------|
| ReAct 推理 | GPT-5 mini | OpenAI | CP 值最高 + Tool Use 夠用 |
| 路由 / 分類 | GPT-5 nano | OpenAI | 最便宜的 tool-capable 模型 |
| Embedding | text-embedding-3-small | OpenAI | 最便宜、生態系最好 |
| 高品質備選 | Claude Sonnet 4.6 | Anthropic | 需要時切換，Tool Use 最強 |
| 長文件備選 | Gemini 3 Flash | Google | 1M context 優勢 |

> **DDD 架構優勢**：LLM Provider 是 Infrastructure 層的實作，切換模型只改設定，不動業務邏輯。每個 Bot 可獨立選模型。

---

## 五、總成本估算（基礎設施 + API）

### 方案 A（Firebase Hosting）+ 推薦 LLM 組合

| 項目 | 月費 (USD) | 月費 (TWD) |
|------|-----------|-----------|
| Cloud Run | ~$0-15 | ~$0-483 |
| Cloud SQL + pgvector | ~$50 | ~$1,610 |
| Memorystore Redis | ~$35 | ~$1,127 |
| Firebase Hosting | ~$0-5 | ~$0-161 |
| VPC + Registry + Others | ~$8.5 | ~$274 |
| **基礎設施小計** | **~$93-113** | **~$3,000-3,640** |
| | | |
| LLM API（GPT-5 mini 推薦組合） | ~$0.2-1.2 | ~$6-39 |
| LLM API（Claude Sonnet 高品質） | ~$2-10 | ~$64-322 |
| | | |
| **總計（推薦組合）** | **~$93-115** | **~$3,000-3,700** |
| **總計（高品質組合）** | **~$95-123** | **~$3,060-3,960** |

### 年費估算

| 方案 | 月費 | 年費 (USD) | 年費 (TWD) |
|------|------|-----------|-----------|
| 方案 A + 推薦 LLM | ~$93-115 | ~$1,116-1,380 | ~$35,900-44,400 |
| 方案 A + 高品質 LLM | ~$95-123 | ~$1,140-1,476 | ~$36,700-47,500 |
| 方案 B + 推薦 LLM | ~$113-135 | ~$1,356-1,620 | ~$43,600-52,200 |

---

## 六、結論與建議

### 基礎設施

**選方案 A（Firebase Hosting）**，年省 $240-300，初始設定 5 分鐘，零維運。

### LLM 供應商

**建議混合使用，主力 OpenAI**：

| 決策 | 建議 |
|------|------|
| 公司只允許一家供應商 | **OpenAI**（GPT-5 mini + nano + embedding）— 一張帳單搞定 |
| 公司允許多家供應商 | **OpenAI 主力 + Anthropic 備選** — 最佳品質彈性 |

### ReAct Agent 模型

| 需求 | 推薦模型 | 月 API 費 |
|------|---------|----------|
| **CP 值最高（推薦）** | GPT-5 mini | ~$0.2-1 |
| **品質最強** | Claude Sonnet 4.6 | ~$2-10 |
| **最便宜** | Gemini 3 Flash | ~$0.1-0.5 |

> **定價基準日**：2026-03-16
> **資料來源**：GCP / OpenAI / Anthropic / Google 官方定價頁面
