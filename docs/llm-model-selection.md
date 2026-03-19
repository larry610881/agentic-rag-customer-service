# LLM / Embedding 模型選型報告

> 更新日期：2026-03-15
> 排除大陸廠商模型（DeepSeek、Qwen、GLM 等）

## 一、LLM 模型完整清單

### 旗艦級（最強推理能力）

| 模型 | 廠商 | Input $/M tokens | Output $/M tokens | Context | 特色 |
|------|------|------------------|--------------------|---------|------|
| **Gemini 3.1 Pro** | Google | $2.00 | $12.00 | 1M | Benchmark #1（並列），多模態 |
| **GPT-5.2** | OpenAI | $1.75 | $14.00 | 128K | Benchmark #1（並列） |
| **Claude Opus 4.6** | Anthropic | $5.00 | $25.00 | 1M | 最強程式碼 + 長文理解 |
| **Claude Sonnet 4.6** | Anthropic | $3.00 | $15.00 | 1M | 接近 Opus 品質，價格 60% |

### 高性價比（推理能力強 + 價格合理）

| 模型 | 廠商 | Input $/M tokens | Output $/M tokens | Context | CP 值評估 |
|------|------|------------------|--------------------|---------|----------|
| **Gemini 3 Flash** | Google | $0.50 | $3.00 | 1M | **最佳 CP** — 旗艦 80% 品質、5% 價格 |
| **GPT-5 mini** | OpenAI | $0.25 | $2.00 | 128K | 比 GPT-4o-mini 更強，價格持平 |
| **Gemini 2.5 Flash** | Google | $0.30 | $2.50 | 1M | 穩定可靠，1M context |
| **Claude Haiku 4.5** | Anthropic | $1.00 | $5.00 | 200K | Anthropic 最便宜，品質仍好 |

### 超低成本（大量呼叫 / 簡單任務）

| 模型 | 廠商 | Input $/M tokens | Output $/M tokens | Context | 適用場景 |
|------|------|------------------|--------------------|---------|---------|
| **GPT-5 nano** | OpenAI | $0.05 | $0.40 | 128K | 分類、摘要、簡單 QA |
| **Gemini 2.5 Flash-Lite** | Google | $0.10 | $0.40 | 1M | 超低成本 + 長 context |
| **Gemini 2.0 Flash-Lite** | Google | $0.075 | $0.30 | 1M | 最便宜（⚠️ 2026/06/01 停用） |
| **GPT-4o-mini** | OpenAI | $0.15 | $0.60 | 128K | 穩定成熟，大量生產驗證 |

### 注意事項

- **Gemini 2.0 Flash 即將 2026/06/01 停用**，應遷移到 2.5 Flash 或 3 Flash
- GPT-5.2 Pro（$21/$168）為超高價高品質版，一般場景不需要
- Claude Opus 4.6 Fast Mode（$30/$150）為低延遲版，一般不需要

---

## 二、Embedding 模型清單

| 模型 | 廠商 | $/M tokens | 維度 | 特色 |
|------|------|-----------|------|------|
| **text-embedding-3-small** | OpenAI | $0.02 | 1536 | **最便宜**，品質足夠 |
| **text-embedding-3-large** | OpenAI | $0.13 | 3072 | 更高精度，多數場景不需要 |
| **Gemini Embedding 2** | Google | $0.20 | 3072 | 多模態（圖/音/影），text-embedding-004 已棄用 |
| **Voyage 3.5** | Voyage AI | $0.06 | 1024 | 高品質，**免費額度 200M tokens** |

### Embedding 選型建議

| 場景 | 推薦 | 理由 |
|------|------|------|
| 一般文字 RAG | **text-embedding-3-small** | 最便宜、品質足夠、生態系最好 |
| 高精度需求 | text-embedding-3-large | 品質更好但價格 6.5x |
| 新專案試水 | **Voyage 3.5** | 免費額度 200M tokens |
| 多模態需求 | Gemini Embedding 2 | 唯一支援圖/音/影 |

---

## 三、成本省錢技巧

| 技巧 | 節省幅度 | 說明 | 支援廠商 |
|------|---------|------|---------|
| **Batch API** | -50% | 非即時任務批次處理，24hr SLA | OpenAI, Anthropic, Google |
| **Prompt Caching** | -90% | 重複 system prompt 只算 0.1x | OpenAI, Anthropic, Google |
| **Batch + Caching 組合** | -95% | 非即時場景（摘要、批次分析）適用 | All |
| **小模型做簡單任務** | -80~95% | 分類/路由用 nano，推理用 Flash/mini | All |
| **Context 精簡** | -30~50% | 減少不必要的 context（精準 RAG retrieval） | All |

### Prompt Caching 比較

| 廠商 | Cache 機制 | Cache 讀取費用 | 最低 cache 長度 |
|------|-----------|-------------|----------------|
| OpenAI | 自動 cache（1024 tokens prefix match） | Input 價格的 50% | 1,024 tokens |
| Anthropic | 手動標記 cache breakpoint | Input 價格的 10% | 1,024 tokens |
| Google | 自動 + 手動 Context Caching | 按快取時間計費 | 32,768 tokens |

---

## 四、模型能力排名（2026/03 綜合評估）

### 綜合推理能力

```
Tier 1（旗艦）：
  Gemini 3.1 Pro ≈ GPT-5.2 > Claude Opus 4.6 > Claude Sonnet 4.6

Tier 2（高性價比）：
  Gemini 3 Flash > GPT-5 mini > Gemini 2.5 Flash > Claude Haiku 4.5

Tier 3（超低成本）：
  GPT-5 nano > Gemini 2.5 Flash-Lite ≈ GPT-4o-mini > Gemini 2.0 Flash-Lite
```

### Function Calling / Tool Use 能力

```
最強：Claude Sonnet 4.6 ≈ GPT-5.2 > Gemini 3.1 Pro
高 CP：GPT-5 mini > Gemini 3 Flash > Claude Haiku 4.5
低成本：GPT-5 nano > GPT-4o-mini（其餘不建議用於 tool use）
```

### RAG 回答品質（含引用準確度）

```
最強：Claude Sonnet 4.6 > GPT-5.2 > Gemini 3.1 Pro
高 CP：GPT-5 mini > Gemini 3 Flash > Claude Haiku 4.5
低成本：GPT-5 nano > Gemini 2.5 Flash-Lite
```

### 多語言支援（中/英/日）

```
最強：Gemini 3.1 Pro > GPT-5.2 > Claude Opus 4.6
高 CP：Gemini 3 Flash > GPT-5 mini > Claude Haiku 4.5
```

---

## 五、agentic-rag 選型建議

### 保留的 Provider 與模型

```
保留：
├── OpenAI
│   ├── GPT-5 mini        ← 主力 LLM（CP 值最高）
│   ├── GPT-5 nano        ← 簡單任務（分類、路由、摘要）
│   └── text-embedding-3-small  ← Embedding（最便宜）
│
├── Google Gemini
│   ├── Gemini 3 Flash    ← 備選主力（1M context 優勢）
│   └── Gemini 2.5 Flash-Lite ← 超低成本簡單任務
│
└── Anthropic Claude
    ├── Claude Sonnet 4.6  ← 高品質需求時切換
    └── Claude Haiku 4.5   ← 中等品質 + 中等價格
```

### 移除的 Provider

```
移除：
├── DeepSeek（大陸廠商）
├── Qwen（大陸/阿里巴巴）
└── OpenRouter（不直接用，透過原廠 API）
```

### 分層使用策略

| 用途 | 推薦模型 | 備選 | 月費估算（單租戶低用量） |
|------|---------|------|----------------------|
| **Agent 對話推理** | GPT-5 mini | Gemini 3 Flash | ~$0.2-1.0 |
| **意圖分類/路由** | GPT-5 nano | Gemini 2.5 Flash-Lite | ~$0.01-0.05 |
| **RAG 回答生成** | GPT-5 mini | Claude Haiku 4.5 | ~$0.2-1.0 |
| **長文件摘要** | Gemini 3 Flash（1M ctx） | Claude Sonnet 4.6 | ~$0.1-0.5 |
| **高品質客製需求** | Claude Sonnet 4.6 | Gemini 3.1 Pro | ~$2-10 |
| **Embedding** | text-embedding-3-small | Voyage 3.5 | ~$0.02-0.1 |

### 單租戶 API 月費方案

| 方案 | LLM 選擇 | Embedding | API 月費 |
|------|---------|-----------|---------|
| **最省** | GPT-5 nano + Gemini 2.5 Flash-Lite | text-embedding-3-small | **~$0.1-1** |
| **推薦** | GPT-5 mini（主）+ GPT-5 nano（路由） | text-embedding-3-small | **~$0.5-3** |
| **高品質** | Claude Sonnet 4.6 + GPT-5 nano（路由） | text-embedding-3-small | **~$4-20** |

---

## 六、模型遷移計畫

### 需注意的 EOL（End of Life）

| 模型 | 停用日期 | 遷移目標 |
|------|---------|---------|
| Gemini 2.0 Flash | 2026/06/01 | Gemini 2.5 Flash 或 3 Flash |
| Gemini 2.0 Flash-Lite | 2026/06/01 | Gemini 2.5 Flash-Lite |
| text-embedding-004 (Google) | 已棄用 | Gemini Embedding 2 |

### 建議的遷移策略

1. **不要依賴即將停用的模型**：新開發直接用 2.5+ 或 3.x 系列
2. **保持 Provider 抽象層**：透過 Port/Adapter 模式（專案已有）輕鬆切換
3. **每季回顧**：每季檢查模型價格變動和新模型上市
4. **A/B 測試**：重大模型切換前做 A/B 品質測試

---

## 七、定價來源

| 廠商 | 定價頁面 |
|------|---------|
| OpenAI | https://openai.com/pricing |
| Anthropic | https://www.anthropic.com/pricing |
| Google | https://ai.google.dev/pricing |
| Voyage AI | https://www.voyageai.com/pricing |

> 定價數據截止日期：2026-03-15。各廠商價格可能隨時調整，建議每月查閱最新定價。
