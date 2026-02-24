# LLM API 參數完整指南

> 最後更新：2026-02-24
>
> 參考來源：[Anthropic Claude Messages API](https://platform.claude.com/docs/en/api/messages)、[OpenAI Chat Completions API](https://platform.openai.com/docs/api-reference/chat/create)、[Google Gemini generateContent API](https://ai.google.dev/api/generate-content)

---

## 目錄

1. [生成控制類](#1-生成控制類)
2. [輸出長度類](#2-輸出長度類)
3. [對話與上下文類](#3-對話與上下文類)
4. [工具呼叫類](#4-工具呼叫類)
5. [推理深度類](#5-推理深度類)
6. [輸出格式類](#6-輸出格式類)
7. [基礎設施類](#7-基礎設施類)
8. [本專案建議暴露的參數](#8-本專案建議暴露的參數)

---

## 1. 生成控制類

控制模型「如何選擇下一個 token」，直接影響回覆的創意度、多樣性和一致性。

### 1.1 temperature

| 項目 | 說明 |
|------|------|
| 用途 | 控制輸出的隨機性（聯想程度） |
| Claude | `0.0 ~ 1.0`，預設 `1.0` |
| OpenAI | `0.0 ~ 2.0`，預設 `1.0` |
| Gemini | `0.0 ~ 2.0` |
| 原理 | 生成時對每個 token 的機率分佈做「溫度縮放」。低溫 → 機率集中在高機率 token → 確定性輸出；高溫 → 機率分散 → 多樣化輸出 |

**深度應用場景**

| temperature | 效果 | 適用場景 |
|-------------|------|---------|
| 0.0 | 每次輸出幾乎相同 | 資料抽取、分類、SQL 生成、JSON 結構化輸出 |
| 0.1 ~ 0.3 | 微幅變化，高度可預測 | **客服問答**、FAQ、知識庫查詢、合約審閱 |
| 0.4 ~ 0.7 | 平衡創意與準確 | 一般對話、摘要、翻譯、郵件撰寫 |
| 0.8 ~ 1.0 | 創意發散 | 腦力激盪、文案發想、故事創作 |
| 1.0 ~ 2.0 | 高度隨機（僅 OpenAI/Gemini） | 實驗用途、詩歌、極端創意需求 |

**注意事項**
- `temperature` 和 `top_p` 建議只調其一，不要同時設定
- OpenAI 的 o 系列推理模型固定 `temperature=1`，不可調整

---

### 1.2 top_p（Nucleus Sampling）

| 項目 | 說明 |
|------|------|
| 用途 | 從累積機率前 p% 的 token 集合中隨機選取 |
| Claude | `0.0 ~ 1.0` |
| OpenAI | `0.0 ~ 1.0`，預設 `1.0` |
| Gemini | `0.0 ~ 1.0` |
| 原理 | 將所有 token 按機率從高到低排列，保留累積機率達到 `top_p` 的最小集合，僅從這個集合中採樣 |

**深度應用場景**

| top_p | 效果 | 適用場景 |
|-------|------|---------|
| 0.1 | 幾乎只選最高機率的 token | 事實型問答、數據報告 |
| 0.3 ~ 0.5 | 少量多樣性，仍高度可靠 | **客服問答**、技術文件 |
| 0.7 ~ 0.9 | 中度多樣性 | 一般對話、郵件 |
| 1.0 | 不做過濾，等同僅由 temperature 控制 | 預設值 |

**與 temperature 的差異**
- `temperature` 改變機率分佈的形狀（平滑 vs 尖銳）
- `top_p` 直接截斷低機率 token，不改變留下 token 的相對機率
- 實務上 `temperature` 較直覺，`top_p` 較精確

---

### 1.3 top_k

| 項目 | 說明 |
|------|------|
| 用途 | 只從機率最高的 K 個 token 中選取 |
| Claude | 支援（進階用途） |
| OpenAI | **不支援** |
| Gemini | 支援 |
| 原理 | 硬截斷：無論機率分佈如何，只保留前 K 個候選 |

**深度應用場景**

| top_k | 效果 | 適用場景 |
|-------|------|---------|
| 1 | 等同 greedy decoding | 數學計算、程式碼生成 |
| 5~20 | 極少量候選，高一致性 | 結構化輸出、填表 |
| 40~100 | 適度多樣性 | 一般對話 |
| 不設定 | 由 temperature / top_p 控制 | 大多數場景 |

---

### 1.4 frequency_penalty（頻率懲罰）

| 項目 | 說明 |
|------|------|
| 用途 | 依據 token 在已生成文字中的**出現次數**，按比例降低其被選中的機率 |
| Claude | **不支援** |
| OpenAI | `-2.0 ~ 2.0`，預設 `0` |
| Gemini | `0.0 ~ 2.0` |
| 原理 | 出現 3 次的 token 受到的懲罰是出現 1 次的 3 倍 |

**深度應用場景**

| 值 | 效果 | 適用場景 |
|----|------|---------|
| 0 | 不懲罰 | 技術文件（專有名詞需重複） |
| 0.3 ~ 0.5 | 輕微減少重複 | **客服回覆**（避免機器感） |
| 0.8 ~ 1.2 | 明顯減少重複用詞 | 文章撰寫、行銷文案 |
| 1.5 ~ 2.0 | 極度避免重複，可能影響流暢度 | 創意寫作實驗 |
| 負值 | 鼓勵重複 | 歌詞、詩歌押韻 |

---

### 1.5 presence_penalty（存在懲罰）

| 項目 | 說明 |
|------|------|
| 用途 | 只要 token 已出現過（不論次數），一律施加固定懲罰 |
| Claude | **不支援** |
| OpenAI | `-2.0 ~ 2.0`，預設 `0` |
| Gemini | `0.0 ~ 2.0` |
| 原理 | 二元開關：出現過 = 扣分，沒出現過 = 不扣分。不像 frequency_penalty 累加 |

**深度應用場景**

| 值 | 效果 | 適用場景 |
|----|------|---------|
| 0 | 不懲罰 | 預設值 |
| 0.3 ~ 0.6 | 鼓勵引入新詞彙和話題 | **客服對話**（避免迴圈回覆） |
| 1.0 ~ 1.5 | 強制話題轉換 | 腦力激盪 |
| 負值 | 鼓勵停留在同一話題 | 深入分析單一主題 |

**frequency_penalty vs presence_penalty**
- `frequency_penalty`：「你已經說了 3 次這個詞，少用一點」→ 按次數遞增
- `presence_penalty`：「你提過這個詞了，換個新的」→ 一次性固定懲罰
- 搭配使用：`frequency_penalty=0.3 + presence_penalty=0.3` 可兼顧減少重複又引入新話題

---

### 1.6 seed

| 項目 | 說明 |
|------|------|
| 用途 | 固定隨機種子，讓相同輸入產生（接近）相同輸出 |
| Claude | **不支援** |
| OpenAI | integer（Beta） |
| Gemini | integer |
| 原理 | 控制採樣的隨機數生成器初始值。但各家都不保證 100% 確定性 |

**深度應用場景**
- **A/B 測試**：固定 seed 比對不同 prompt 的效果差異
- **回歸測試**：確保 prompt 調整後結果可重現
- **除錯**：重現用戶回報的問題回覆
- **合規審計**：保留可重現的決策記錄

---

## 2. 輸出長度類

### 2.1 max_tokens / max_completion_tokens / maxOutputTokens

| 項目 | 說明 |
|------|------|
| 用途 | 限制模型最大輸出 token 數 |
| Claude | `max_tokens`（必填） |
| OpenAI | `max_completion_tokens`（取代已棄用的 `max_tokens`） |
| Gemini | `maxOutputTokens` |
| 原理 | 硬上限，模型可能在此之前自然停止 |

**深度應用場景**

| 值 | 場景 | 說明 |
|----|------|------|
| 50~150 | 分類/標籤/情緒分析 | 只需短回覆 |
| 256~512 | **客服簡答** | 一般問答足夠 |
| 1024~2048 | **客服詳細回覆** | 退貨流程、操作教學 |
| 4096+ | 長文生成 | 文章、報告、程式碼 |

**成本控制**：token 數直接影響費用，設定合理上限可避免意外高額帳單。

---

### 2.2 stop_sequences / stop / stopSequences

| 項目 | 說明 |
|------|------|
| 用途 | 遇到指定字串時立即停止生成 |
| Claude | `stop_sequences`（string 陣列） |
| OpenAI | `stop`（最多 4 個） |
| Gemini | `stopSequences` |

**深度應用場景**
- **結構化輸出**：以 `"\n\n"` 或 `"---"` 作為段落分隔停止符
- **對話系統**：以 `"Human:"` 或 `"User:"` 停止，避免模型自導自演
- **程式碼生成**：以 `"\n```"` 停止，避免生成多餘內容
- **JSON 抽取**：以 `"}"` 或 `"]"` 停止，確保完整 JSON 後不多生成

---

## 3. 對話與上下文類

### 3.1 messages / contents（對話歷史）

| 項目 | 說明 |
|------|------|
| 用途 | 傳入完整對話歷史，讓模型理解上下文 |
| Claude | `messages`（最多 100,000 條） |
| OpenAI | `messages` |
| Gemini | `contents` |

**深度應用場景**

對話歷史的長度（即「關聯歷史」）是應用層控制的關鍵參數：

| 歷史長度 | 效果 | 適用場景 | Token 成本 |
|---------|------|---------|-----------|
| 0 | 無記憶，每次獨立 | 單次查詢、分類 | 最低 |
| 3~5 | 短期記憶 | 簡單客服問答 | 低 |
| 10~15 | 中期記憶 | **多步驟客服流程**（退貨引導） | 中 |
| 20~35 | 長期記憶 | 複雜諮詢、技術支援 | 高 |
| 50+ | 完整對話 | 長篇討論、辯論 | 很高 |

**進階策略**
- **滑動視窗**：只保留最近 N 條訊息
- **摘要壓縮**：超過 N 條後，由 LLM 先摘要歷史再帶入
- **選擇性帶入**：用 embedding 搜尋與當前問題最相關的歷史訊息
- **角色過濾**：只帶 assistant 最後回覆 + 所有 user 訊息

---

### 3.2 system / systemInstruction（系統提示詞）

| 項目 | 說明 |
|------|------|
| 用途 | 設定模型的角色、行為規範和回覆格式 |
| Claude | `system`（string 或 TextBlock 陣列） |
| OpenAI | `developer` role 訊息（o 系列）或 `system` role 訊息 |
| Gemini | `systemInstruction` |

**深度應用場景**
- **角色設定**：「你是某某電商的 AI 客服」
- **回覆格式**：「回覆必須以 JSON 格式輸出」
- **行為約束**：「不可回答與電商無關的問題」
- **語言指定**：「請使用繁體中文回覆」
- **安全邊界**：「不可透露內部系統架構」

---

### 3.3 n / candidateCount（候選回覆數）

| 項目 | 說明 |
|------|------|
| 用途 | 一次請求生成多個候選回覆 |
| Claude | **不支援** |
| OpenAI | `n`（1~128，預設 1） |
| Gemini | `candidateCount` |

**深度應用場景**
- **品質篩選**：生成 3 個回覆，由 scoring model 選最佳
- **A/B 測試**：同時生成不同風格的回覆
- **自動評分**：多個回覆互相比較一致性

**注意**：`n > 1` 時費用按候選數量倍增。

---

## 4. 工具呼叫類

### 4.1 tools（工具定義）

| 項目 | 說明 |
|------|------|
| 用途 | 定義模型可使用的外部工具（Function Calling） |
| Claude | `tools`（custom tool, code execution, web search） |
| OpenAI | `tools`（function type） |
| Gemini | `tools`（functionDeclarations） |

**深度應用場景**
- **訂單查詢**：模型判斷用戶意圖後呼叫 `order_lookup` 工具
- **知識檢索**：模型決定何時需要 RAG 查詢
- **外部 API**：查天氣、匯率、庫存等即時資訊
- **程式碼執行**：讓模型寫並執行 Python（Claude Code Execution）
- **多工具協作**：模型自主決定使用哪些工具、以什麼順序

---

### 4.2 tool_choice（工具使用策略）

| 項目 | 說明 |
|------|------|
| 用途 | 控制模型是否及如何使用工具 |
| Claude | `auto`、`any`（必須用某個）、`none`、指定工具名 |
| OpenAI | `auto`、`required`、`none`、指定工具名 |
| Gemini | `toolConfig.functionCallingConfig.mode` |

**深度應用場景**

| 模式 | 說明 | 適用場景 |
|------|------|---------|
| `auto` | 模型自行判斷是否呼叫工具 | **一般客服**（推薦） |
| `any` / `required` | 強制模型必須使用工具 | 資料抽取 pipeline |
| `none` | 禁止使用工具 | 純對話模式 |
| 指定工具名 | 強制使用特定工具 | 明確知道需要哪個工具時 |

---

## 5. 推理深度類（2025-2026 新增）

### 5.1 thinking / thinkingConfig（延伸思考）

| 項目 | 說明 |
|------|------|
| 用途 | 讓模型在回覆前進行「思考鏈」推理 |
| Claude | `thinking: {type: "enabled", budget_tokens: 4096}` |
| OpenAI | 不直接支援（o 系列模型內建） |
| Gemini | `thinkingConfig: {thinkingLevel: "medium"}` |

**深度應用場景**
- **複雜推理**：數學題、邏輯判斷、程式碼 debug
- **長文分析**：合約審閱、法律文件
- **多步驟規劃**：退貨流程決策、客訴升級判斷

**Claude thinking 配額建議**

| budget_tokens | 適用場景 |
|---------------|---------|
| 1024 | 簡單分類和判斷 |
| 4096 | 中等複雜度推理 |
| 8192~16384 | 複雜程式碼生成、數學證明 |

---

### 5.2 reasoning_effort / output effort（推理努力程度）

| 項目 | 說明 |
|------|------|
| 用途 | 不開啟完整 thinking 的前提下，控制模型投入推理的程度 |
| Claude | `output_config.effort`（`low` / `medium` / `high` / `max`） |
| OpenAI | `reasoning_effort`（`low` / `medium` / `high`） |
| Gemini | `thinkingLevel`（`minimal` / `low` / `medium` / `high`） |

**深度應用場景**

| 等級 | 延遲 | 適用場景 |
|------|------|---------|
| low / minimal | 最快 | 簡單分類、情緒偵測、意圖識別 |
| medium | 中等 | **一般客服問答** |
| high | 較慢 | 複雜退貨判斷、客訴分析 |
| max | 最慢 | 法律分析、深度研究 |

---

## 6. 輸出格式類

### 6.1 response_format / responseMimeType（回覆格式）

| 項目 | 說明 |
|------|------|
| 用途 | 強制模型以指定格式輸出 |
| Claude | `output_config.format` |
| OpenAI | `response_format: {type: "json_object"}` |
| Gemini | `responseMimeType: "application/json"` |

**深度應用場景**
- **JSON Mode**：API 中間層需要結構化資料
- **JSON Schema**：強制輸出符合特定 schema，適合資料抽取
- **Text Mode**：自然語言回覆（預設）

---

### 6.2 logprobs（對數機率）

| 項目 | 說明 |
|------|------|
| 用途 | 回傳每個輸出 token 的機率 |
| Claude | **不支援** |
| OpenAI | `logprobs: true`，搭配 `top_logprobs`（0~20） |
| Gemini | **不支援** |

**深度應用場景**
- **信心度評估**：logprob 低的 token = 模型不確定 → 觸發人工審核
- **幻覺偵測**：整體 logprob 偏低的回覆可能是幻覺
- **自動品質控制**：設定 logprob 閾值過濾低品質回覆
- **Prompt 優化**：比較不同 prompt 對關鍵 token 的 logprob 影響

---

## 7. 基礎設施類

### 7.1 stream（串流）

| 項目 | 說明 |
|------|------|
| 用途 | 以 SSE 事件逐步回傳生成結果 |
| Claude | `stream: true` |
| OpenAI | `stream: true` |
| Gemini | streaming endpoint |

**深度應用場景**
- **即時體驗**：用戶看到逐字出現的回覆，感知延遲降低
- **早期中斷**：偵測到不良回覆可提前終止
- **進度指示**：前端顯示「正在回覆...」動畫

---

### 7.2 service_tier（服務等級）

| 項目 | 說明 |
|------|------|
| 用途 | 選擇不同的運算資源等級 |
| Claude | `auto` / `standard_only` |
| OpenAI | `auto` / `default` / `flex`（省錢但慢）/ `priority`（快但貴） |

**深度應用場景**
- **成本優先**：批次處理用 `flex`，非即時場景省 50%+
- **延遲優先**：VIP 客戶用 `priority`，保證低延遲
- **混合策略**：一般客服用 `default`，升級客訴用 `priority`

---

### 7.3 cache_control / prompt_cache（提示快取）

| 項目 | 說明 |
|------|------|
| 用途 | 快取 system prompt 或長上下文，後續請求不重新計算 |
| Claude | `cache_control: {type: "ephemeral"}`（TTL: 5min 或 1hr） |
| OpenAI | `prompt_cache_key` + `prompt_cache_retention` |
| Gemini | `cachedContent` |

**深度應用場景**
- **長 System Prompt**：客服知識庫注入 system prompt 後快取，大幅降低 token 費
- **多輪對話**：對話歷史前半段快取
- **批次處理**：相同 prompt 模板 + 不同用戶輸入

**Claude 快取節費範例**

| 場景 | 無快取 | 有快取 | 節省 |
|------|--------|--------|------|
| 3000 token system prompt × 100 請求 | 300K input tokens | 3K + 99×快取讀取 | ~90% input cost |

---

### 7.4 metadata / user（使用者追蹤）

| 項目 | 說明 |
|------|------|
| 用途 | 追蹤使用者身份（防濫用，不含 PII） |
| Claude | `metadata.user_id` |
| OpenAI | `user` |

---

## 8. 本專案建議暴露的參數

### 8.1 管理員可調參數（後台設定頁面）

應暴露給租戶管理員（Tenant Admin），儲存在 DB 作為租戶級設定：

| 對外名稱 | API 參數 | 建議範圍 | 預設值 | UI 元件 | 說明 |
|----------|---------|---------|--------|---------|------|
| 聯想等級 | `temperature` | 0 ~ 1（步進 0.1） | `0.3` | Slider | 越低越精準，越高越發散 |
| 關聯歷史 | 應用層截斷長度 | 0 ~ 35 | `10` | Slider | 帶入對話歷史的訊息數上限 |
| 回覆長度上限 | `max_tokens` | 128 ~ 4096 | `1024` | Slider | 單次回覆最大 token 數 |
| 推理深度 | `reasoning_effort` | low / medium / high | `medium` | Select | 越深延遲越高但品質更好 |
| 重複懲罰 | `frequency_penalty` | 0 ~ 1（步進 0.1） | `0` | Slider | 減少重複用詞 |

### 8.2 系統級參數（`.env` 設定，不暴露給使用者）

| 參數 | 建議值 | 說明 |
|------|--------|------|
| `stream` | `true` | 始終開啟串流 |
| `tools` | 由 DI Container 注入 | 工具定義不可讓使用者改 |
| `tool_choice` | `auto` | 讓模型自行判斷 |
| `system` | 由 system prompt 模板管理 | 注入租戶資訊 + 安全邊界 |
| `service_tier` | `auto` | 使用預設服務等級 |
| `cache_control` | `ephemeral` (5min) | 長 system prompt 快取 |

### 8.3 完全不暴露的參數

| 參數 | 原因 |
|------|------|
| `top_p`、`top_k` | 與 `temperature` 功能重疊，暴露太多造成混淆 |
| `presence_penalty` | 與 `frequency_penalty` 功能接近，只留一個 |
| `seed` | 客服場景不需要重現性控制 |
| `logprobs` | 開發/偵錯用，不適合終端使用者 |
| `n` / `candidateCount` | 客服不需多候選回覆，浪費費用 |
| `stop_sequences` | 技術參數，錯誤設定會導致回覆截斷 |

### 8.4 實作架構

```
┌──────────────────────────────────────────┐
│  前端管理後台（Settings 頁面）              │
│  ┌─────────┐ ┌──────────┐ ┌───────────┐  │
│  │聯想等級  │ │關聯歷史   │ │回覆長度上限│  │
│  │  0.3    │ │  10      │ │  1024     │  │
│  └─────────┘ └──────────┘ └───────────┘  │
└───────────────────┬──────────────────────┘
                    │ API: PUT /api/v1/tenants/:id/settings
                    ▼
┌──────────────────────────────────────────┐
│  後端 TenantSettings（DB per-tenant）      │
│  {                                        │
│    temperature: 0.3,                      │
│    history_limit: 10,                     │
│    max_tokens: 1024,                      │
│    reasoning_effort: "medium",            │
│    frequency_penalty: 0                   │
│  }                                        │
└───────────────────┬──────────────────────┘
                    │ SendMessageUseCase.execute()
                    ▼
┌──────────────────────────────────────────┐
│  LLM API 呼叫                             │
│                                           │
│  messages = history[-settings.limit:]     │ ← 關聯歷史截斷
│  temperature = settings.temperature       │ ← 聯想等級
│  max_tokens = settings.max_tokens         │ ← 回覆長度
│  ...其餘由系統決定                          │
└──────────────────────────────────────────┘
```

---

## 參考資料

- [Anthropic Claude Messages API](https://platform.claude.com/docs/en/api/messages)
- [OpenAI Chat Completions API](https://platform.openai.com/docs/api-reference/chat/create)
- [Google Gemini generateContent API](https://ai.google.dev/api/generate-content)
- [Google Vertex AI Content Generation Parameters](https://docs.cloud.google.com/vertex-ai/generative-ai/docs/multimodal/content-generation-parameters)
- [LLM Parameters Explained](https://learnprompting.org/blog/llm-parameters)
