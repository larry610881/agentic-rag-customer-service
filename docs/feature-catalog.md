# 平台功能目錄（業務 PPT 來源稿）

> 用途：業務向客戶介紹「我們有什麼功能 / 能做到什麼」的 source of truth。
> 不是 roadmap、不是技術規格、不是工程任務清單。
> 每次 sprint 完成或功能上下架時同步更新。
>
> PPT 結構建議：
> ```
> 封面 → 平台一句話定位 → 九大模組總覽（一頁俯視圖）
>    ↓
> 每個模組獨立一頁 deep-dive（用本檔的「業務痛點 / 解法 / 細項」三段填）
>    ↓
> 2-3 個 User Journey 故事（demo 場景，文末有範例）
>    ↓
> （選配）未來發展 1 頁
> ```

---

## 一句話定位

> **企業級 RAG AI 客服平台 — 從文件到客戶，5 分鐘上線。**

替代版本：
- 多租戶 AI 客服 SaaS，內建知識庫、對話 agent、跨通道整合與全鏈路觀測
- 不寫程式也能拉出可上線的智能客服機器人

---

## 九大模組總覽（一頁俯視圖）

| # | 模組 | 業務一句話 | 對客戶的核心價值 |
|---|------|-----------|----------------|
| 1 | 多租戶 + 計費 | SaaS 級租戶隔離、用多少付多少 | 一套系統服務多客戶不互通、成本透明可預測 |
| 2 | RAG 知識引擎 | 文件上傳 → 自動分類 → 智能檢索 | 客戶自己的知識自動變成 AI 大腦 |
| 3 | Bot Studio（視覺化） | 不會寫程式也能拉 agent 流程圖 | 行銷 / 營運自己改 bot，不依賴工程 |
| 4 | AI Agent 引擎 | ReAct 推理迴圈 + 動態 Worker 路由 + 工具編排 | 處理複雜流程而非一問一答 |
| 5 | 多通道整合 | Web Widget / Line / API 共用同一個 bot | 客戶在哪我們就在哪、行為一致 |
| 6 | Prompt 安全防護 | 攔截越獄攻擊 + 輸出敏感詞檢查 | 防止 bot 被綁架、避免敏感資訊外洩 |
| 7 | 對話記憶 | 跨 session 記住用戶偏好與歷史 | 不用每次重新自我介紹、體驗連貫 |
| 8 | 觀測 + 追蹤 | 每筆對話 DAG / Token / 延遲完整紀錄 | 出包能查、計費可稽核、優化有依據 |
| 9 | 治理 + Admin | 系統級管理、定價、quota、診斷規則 | 多租戶營運可控、SLA 可量化 |

---

## 1. 多租戶 + 計費

### 業務痛點
- 一家服務商要同時服務 N 家客戶，但 OpenAI / Anthropic 帳單只看到混在一起的總額
- 不知道哪個客戶用太兇、誰賺錢誰賠錢

### 我們的解法
- DB 層級租戶隔離（每筆資料都帶 tenant_id）
- Append-only Token Ledger 記錄每一次扣量，不會 drift
- 三段式收費（Plan 月費 + Token 套餐 + 超用 add-on auto-topup）

### 細項功能
- ✓ 多租戶完全隔離（DB / Qdrant / 對話 / 知識庫）
- ✓ 三層方案管理（Plan：base + included categories + addon pack）
- ✓ Token Ledger（append-only，跨月 carryover、overage deficit 繼承）
- ✓ 即時配額顯示（系統視角 audit + 租戶視角 billable）
- ✓ Auto-topup 自動加值 + 失敗告警
- ✓ Billing Transactions 完整金流稽核
- ✓ 月度 cron 重置 + 跨年邊界處理
- ✓ 系統收益儀表板（毛利、平台吸收量）

### Demo 截圖
- 租戶 /quota 頁面（看到剩餘 + 已用）
- Admin /quota-overview（並列兩視角）
- Admin /revenue-dashboard

---

## 2. RAG 知識引擎

### 業務痛點
- 客戶有很多 PDF / FAQ / 商品 DM，希望 AI 直接從這些文件回答
- 文件量大時檢索準確度直線下降、客戶常抱怨答非所問

### 我們的解法
- Contextual Retrieval（Anthropic 2024 論文）— 每個 chunk 自動補上下文
- Auto-Classification — 向量聚類 + LLM 自動命名分類，免人工標籤
- Per-KB 模型可選 — 高敏感 KB 用較貴更準的模型，一般 KB 省成本

### 細項功能
- ✓ 三條上傳入口（form / signed URL / confirm — 繞 Cloud Run 32MB 限制）
- ✓ 多檔案格式（PDF / Word / Excel / CSV / JSON / 圖片 OCR）
- ✓ PDF 自動逐頁拆分（catalog 模式）+ Vision OCR
- ✓ Contextual Retrieval（每個 chunk 自動補 1-2 句上下文）
- ✓ Auto-Classification（chunk 自動分類 + LLM 命名）
- ✓ text-embedding-3-large（3072 維，比 small 精度 +35%）
- ✓ DM 圖卡查詢（query_dm_with_image — 直接回 PNG carousel）
- ✓ KB Studio（chunk 編輯 + 修正後 auto re-embed）
- ✓ 跨 KB 檢索（同 bot 綁多個 KB）
- ✓ Quality filter + 去重 + 語言偵測

### Demo 截圖
- 上傳一個 PDF → 看到分頁 / chunk / 自動分類
- KB Studio 編輯一個 chunk
- 對話展開「引用來源」
- LINE 收到 DM PNG carousel

---

## 3. Bot Studio（視覺化編排）

### 業務痛點
- 行銷 / 營運想改 bot 行為，但每次都要 ticket 給工程
- 改完不知道效果，要等用戶實際對話才看得到

### 我們的解法
- 視覺化藍圖：把 bot 的 sub-agent 結構畫成圖
- 即時試運轉：左邊改設定、右邊立刻對話測試
- DAG 即時長出：每個 LLM / Tool / 攔截點都可視化

### 細項功能
- ✓ Bot 配置藍圖（Worker / Tool 結構視覺化）
- ✓ 即時試運轉對話（streaming，不寫進正式對話）
- ✓ 執行時序軸（每筆事件由左→右排列、最新自動置中）
- ✓ 即時 DAG（節點隨對話進行逐步長出）
- ✓ 完整 DAG（最終 layout，含所有節點 + token 用量）
- ✓ 失敗節點紅色 + ping 動畫
- ✓ 攔截事件強紅 ring 顯眼
- ✓ Trace 含工具 input/output / token / latency / error
- ✓ Studio 對話自動標 source=studio 與正式對話分流

### Demo 截圖
- Studio 全頁（藍圖 + 試運轉 + DAG）
- 攔截事件的紅節點
- 跑工具時的 DAG 動畫

---

## 4. AI Agent 引擎

### 業務痛點
- 一問一答型 chatbot 處理不了真實客服流程（多步驟、需要查多個系統、有條件分支）
- 不同類型的問題（閒聊 / 商品 / 退貨）需要不同的人格與知識

### 我們的解法
- ReAct 推理迴圈：LLM 自己決定要呼叫哪個工具、看完結果決定下一步
- Worker 動態路由：根據用戶意圖切換 system_prompt / 啟用工具 / 模型
- 工具編排：知識庫查詢 / DM 圖卡 / 真人轉接 / 自訂 MCP

### 細項功能
- ✓ ReAct 推理迴圈（LLM 自主決定工具 + 多輪推理）
- ✓ 動態 Worker 路由（intent classifier 選 worker → 換 system_prompt + tools）
- ✓ 內建工具：rag_query / query_dm_with_image / transfer_to_human_agent
- ✓ MCP 外部工具整合（SSE 連接 + 自動 schema 載入）
- ✓ Per-bot 模型選擇（多 provider：Anthropic / OpenAI / Google / DeepSeek 等）
- ✓ Per-tool RAG 參數（不同工具不同 top_k / threshold）
- ✓ Worker per-worker 獨立模型 + prompt
- ✓ Tool input/output 全紀錄（trace + diagnostic）
- ✓ Streaming token-by-token 回覆
- ✓ 對話 lock（同一對話禁止並發、防止 race）

### Demo 截圖
- ReAct loop trace（看到 LLM → tool → LLM → answer）
- Worker 切換的 trace 節點
- MCP 工具呼叫畫面

---

## 5. 多通道整合

### 業務痛點
- 客戶在 Line 用習慣 / 公司官網要 Web Widget / API 給合作夥伴 — 多套系統難維護
- 切通道後對話歷史斷層、體驗不一致

### 我們的解法
- 同一個 bot 配置，走任何 channel 都行為一致
- LINE / Web Widget / API 三條入口共用 send_message_use_case
- 對話歷史跨 channel 自動同步（用 visitor_id 關聯）

### 細項功能
- ✓ Web Widget（嵌入官網的浮動聊天視窗）
- ✓ LINE Bot（webhook + Flex Message + 圖卡 carousel）
- ✓ Web Chat（內建客服頁，SSE streaming）
- ✓ REST API（給第三方接入）
- ✓ Per-channel 設定（LINE 是否帶來源、widget 歡迎訊息等）
- ✓ 跨 channel 對話統一儲存
- ✓ Identity source 標記（widget / line / web / studio / api）
- ✓ Widget 嵌入只需 1 行 script tag

### Demo 截圖
- LINE 對話實機畫面（含 Flex 圖卡）
- 官網 Widget 嵌入示意
- 同一對話在不同 channel 接續

---

## 6. Prompt 安全防護

### 業務痛點
- 客戶 bot 被「忽略以上指令」越獄洩露 system prompt
- 內部 API key / 工具定義不小心被 LLM 講出來

### 我們的解法
- 雙向防護：輸入端攔截攻擊、輸出端過濾敏感詞
- 在 LLM 呼叫前 short-circuit（不會浪費 token + 不會被 compromise）
- 全鏈路紀錄：被攔的請求都進 admin 觀測頁

### 細項功能
- ✓ Input regex/keyword 規則（19 條預設 prompt injection 模式）
- ✓ Output keyword 過濾（system prompt 殘片 / API key / 內部表名）
- ✓ Output LLM-based 二次判斷（可選，準確度更高）
- ✓ 攔截前 short-circuit（不浪費 LLM token）
- ✓ Studio 攔截 banner + DAG 紅節點 + 強紅時序卡
- ✓ 端使用者（Line / Web）只看到 blocked_response，不暴露防禦機制
- ✓ 攔截紀錄完整可查（時間 / 規則 / 用戶訊息 / AI 回應）
- ✓ Per-tenant 規則可擴充

### Demo 截圖
- Studio 試運轉攔截示範
- Admin 攔截紀錄表（展開看完整訊息）
- DAG 紅色 ShieldAlert 節點

---

## 7. 對話記憶

### 業務痛點
- 用戶每次來都要重新自我介紹（生日 / 過敏 / 偏好）
- AI 不記得上週講過的事，體驗斷層

### 我們的解法
- 對話結束後 LLM 自動抽取「值得記憶」的事實
- 下次對話自動載入記憶當 context
- 對話達門檻自動產 LLM summary 取代過長歷史

### 細項功能
- ✓ 自動 memory extraction（對話達門檻觸發）
- ✓ 跨 session 自動載入記憶
- ✓ 對話 summary（壓縮長歷史 + 保留語義）
- ✓ 記憶可手動編輯 / 刪除
- ✓ Per-bot 記憶開關（敏感場域可關）
- ✓ Per-bot extraction prompt 可客製
- ✓ Identity 解析（visitor_id 跨 channel 對應同一人）

### Demo 截圖
- 第一次對話告訴 bot 偏好
- 隔天再來，bot 主動引用之前的偏好
- Admin /memory 頁面看記憶條目

---

## 8. 觀測 + 追蹤

### 業務痛點
- 用戶說「答錯了」但沒辦法重現、不知道哪個工具回了什麼
- Token 用量爆表沒人發現、超支才知道
- 對話品質下降但找不到根因

### 我們的解法
- 每筆對話完整 DAG（哪個 LLM、調哪個工具、拿到什麼資料）
- 每個節點 token / latency / error 全紀錄
- 對話 + 引用 chunks + 用戶 feedback 三層關聯，找錯有依據

### 細項功能
- ✓ Agent execution trace（DAG 節點 + 時序）
- ✓ Token 用量分段（input / output / cache_read / cache_creation）
- ✓ 真實成本估算（per-model pricing 即時計算）
- ✓ Per-conversation token 分析（看哪段燒最多）
- ✓ 對話歷史回放（含 retrieved chunks + tool 輸出）
- ✓ Feedback 收集（按讚 / 倒讚）+ 關聯 chunk
- ✓ Diagnostic rules（自動標記低品質對話）
- ✓ Error tracking（自動分類 + 通知）
- ✓ 系統日誌 + 日誌清理排程

### Demo 截圖
- 一筆對話的完整 DAG 展開
- Token 用量按時間 / 按 bot 圖表
- Diagnostic rule 標記的低品質對話列表

---

## 9. 治理 + Admin

### 業務痛點
- 多租戶 SaaS 上線後 admin 工作爆量（改方案 / 換定價 / 處理告警 / 看誰超支）
- 沒有控制中心 → 工程被瑣事淹沒

### 我們的解法
- 系統級 admin console，所有 SaaS 營運操作集中
- 變更計費 / 方案有完整 audit trail，誰改的可查
- 通知 + 告警自動化，不用人工巡

### 細項功能
- ✓ 租戶 CRUD + 計費 plan 綁定
- ✓ Plan 範本管理（base / addon / 適用 categories）
- ✓ Pricing 版本化管理（含回溯重算）
- ✓ Token 用量總覽 + 分租戶分 bot 鑽取
- ✓ 額度事件追蹤（auto-topup / overage / 跨月 reset）
- ✓ Provider Settings（API key 加密儲存 + multi-provider）
- ✓ MCP 工具庫（系統級工具池 + per-bot 開關）
- ✓ Speed limiter（rate limit 防爆量）
- ✓ 通知渠道（SendGrid / 多 admin email）
- ✓ Admin 帳號管理 + 跨租戶查詢權限

### Demo 截圖
- Admin 首頁概覽
- 修改一個方案的定價 → 看到 audit log
- 收到 quota 告警 email

---

## User Journey 故事範例（PPT 末段用）

### 故事 A：5 分鐘上線一個新客戶 bot
1. Admin 建立租戶「ABC 公司」+ 綁 Starter plan
2. ABC 上傳 50 頁 FAQ PDF → 系統自動 OCR + chunk + 分類
3. ABC 在 Studio 拉一個 bot，綁這個 KB
4. Studio 試運轉幾句測試 → DAG 顯示正確檢索
5. 嵌入 1 行 script tag 到 ABC 官網 → 上線

### 故事 B：發現問題到修正只要 10 分鐘
1. Admin 收到 diagnostic 告警「ABC bot 過去 24h L1 評分下降」
2. 點進去看到具體哪幾筆對話分數低
3. 展開引用 chunks → 發現某個 chunk 內容過時
4. 點「修正」跳到 KB Studio
5. 編輯 chunk → 自動 re-embed → 後續對話品質回升

### 故事 C：客戶想自己微調 bot 個性
1. ABC 行銷想讓 bot 講話更輕鬆
2. 進 Studio 切到「LLM 與 Prompt」分頁
3. 改 system prompt + 改 temperature
4. 立刻試運轉對話確認語氣
5. 滿意後存檔，正式對話立即生效，不用 deploy

---

## 未來發展（PPT 選配 1 頁，可省略）

> 注意：這頁不要在業務 PPT 強調，避免被當「承諾」。寫成「持續優化方向」即可。

| 方向 | 業務價值 |
|---|---|
| Hybrid Retrieval（向量 + BM25 + Rerank） | 檢索精度進一步提升 |
| 自動 Evaluation Pipeline | 品質回歸自動偵測，bot 改了不會偷偷變差 |
| Visual Bot Builder 拖拉編輯 | 行銷可以拖拉節點建 workflow，更直觀 |
| Multi-modal（語音 / 影像直接對話） | 接 Line 語音訊息、客戶傳照片問答 |

---

## 製作 PPT 的工具建議

| 工具 | 適合場景 | 把這份檔案餵進去 |
|---|---|---|
| **Gamma** | 5 分鐘自動生整套 PPT、AI 自動配圖 | 直接貼整份 markdown |
| **Beautiful AI** | 模板美觀、有商業圖庫 | 一頁一頁複製模組區段 |
| **Marp** | 工程師慣用的 markdown → PPT | 加 marp YAML 直接 export |
| **Slidev** | 進階互動投影片 + code 高亮 | 適合技術 demo 場景 |

業務場景推薦 **Gamma**，5 分鐘出第一版再人工微調。
