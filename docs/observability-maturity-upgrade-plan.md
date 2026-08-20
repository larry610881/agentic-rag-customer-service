# 可觀測性成熟度升級計畫（學習 × 討論 × 實作）

> 目的：把自建觀測系統從「POC 完整」推進到「可交付客戶」等級的三項升級——
> ① OTel 對齊、② CI eval 閘門、③ PII 遮罩與保留期限。
> 每項分四段：**要學什麼 → 業界怎麼做 → 我們的現況 → 分階段方案**，文末是實作前要討論的決策清單。
> 狀態：v0.1 學習討論稿（2026-08-20），尚未動工。

---

## 第一項｜OTel GenAI 對齊：讓 trace 講業界的語言

### 1A. 要學什麼

**OpenTelemetry（OTel）三支柱與 trace 核心概念**

| 概念 | 一句話 | 對照我們現有的 |
|------|------|------|
| Trace | 一次請求的完整因果鏈，全域唯一 `trace_id` | `agent_execution_traces.trace_id` ✅ 已有 |
| Span | 有起訖時間的**區間**，可巢狀（parent span） | `ExecutionNode` ≈ span，但扁平 list + `parent_id`，非真巢狀 |
| Event | 掛在 span 上的**時間點**（零長度） | 我們的 `first_token`、`guard_blocked` 其實是 Event，卻用同一個 `add_node()` 混進 span（architecture-journal 已自我點名） |
| Context Propagation | `traceparent` HTTP header（W3C 標準）把 trace_id 帶進下游服務 | ❌ 完全沒有——trace 進不了 MCP server、背景 worker |
| Span Attributes | span 上的 key-value 標籤 | `ExecutionNode.metadata{}` ✅ 概念相同 |

**GenAI Semantic Conventions**（OTel 為 LLM 應用定的標準屬性名，仍在演進但主幹已穩定）：

- 操作類型：`gen_ai.operation.name` = `chat` / `execute_tool` / `embeddings` / `invoke_agent` / `retrieve`（我們的 `node_type` 幾乎一一對應）
- 模型與用量：`gen_ai.request.model`、`gen_ai.response.model`、`gen_ai.usage.input_tokens` / `output_tokens`
- 內容捕捉：`gen_ai.input.messages` / `gen_ai.output.messages` —— 規範明確標注 **opt-in（預設不捕捉全文）**，這直接呼應第三項的遮罩問題
- Agent 相關：`gen_ai.agent.name`、`gen_ai.tool.name`

**Langfuse 資料模型**（開源、可自架，業界開源標準）：

```
Trace（一次互動）
 └─ Observation（三種：SPAN 區間 / GENERATION 帶 model+token 的 LLM 呼叫 / EVENT 時間點）
     └─ 可巢狀
Session（多輪對話分組）← 對照我們的 conversation_id
Score（掛在 trace/observation 上的評分）← 對照我們的 rag_evaluations
Prompt（版本化的 prompt registry）← 我們缺（bots.base_prompt 直接改 DB 欄位，無歷史）
```

關鍵事實：**Langfuse 原生支援 OTLP ingestion**（OTel 的傳輸協定）。也就是說：只要我們的 collector 說 OTel 語言，「要不要用 Langfuse 的 UI」變成隨插隨用的選項，不是重寫。

**動手練習（建議順序）**
1. Docker 自架 Langfuse（`docker compose up`，官方 repo 有現成 compose），建一個 project 拿到 keys。
2. 用 `opentelemetry-sdk` + `opentelemetry-exporter-otlp` 寫 30 行 Python：手動開一個 parent span + 兩個 child span，OTLP 打進 Langfuse，看 UI 長什麼樣。
3. 對照著看：同一個互動在我們 React Flow DAG 和 Langfuse 瀑布圖各自呈現什麼、缺什麼——這個對照會直接告訴你我們 UI 的護城河在哪（領域語意節點、即時 trace），以及該借的是什麼（巢狀、跨服務）。

### 1B. 我們的現況（探索結果彙整）

- Collector：`src/infrastructure/observability/agent_trace_collector.py`，ContextVar 作用域、static method、相對毫秒 offset（`time.monotonic()`）。
- 資料模型：`domain/observability/agent_trace.py` 的 `ExecutionNode`——扁平 list、`parent_id` 自引用、Span/Event 混用。
- 持久化：`send_message_use_case.py:1170` 與 `handle_webhook_use_case.py:960`（LINE）**兩份重複實作**，drift 風險。
- 斷鏈：`request_logs.request_id` 與 `agent_execution_traces.trace_id` **無關聯欄位**，HTTP log 對不上 agent trace。
- 盲區：背景 worker 的 LLM 呼叫（OCR、contextual retrieval、摘要、embedding）有計費（`token_usage_records`）但**完全沒有 trace**。
- 資產（別丟）：領域語意 node_type、串流中即時 DAG（`live-trace-graph.tsx`）、per-chunk 檢索可觀測性、fail-open 寫入紀律、pure-ASGI middleware 的 ContextVar 正確性。

### 1C. 分階段方案

**P1（小、先做）：request_id ⇄ trace_id 關聯**
- `agent_execution_traces` 加 `request_id` 欄位；`AgentTraceCollector.start()` 時從 structlog contextvars 取當前 request_id 寫入。
- 反向：`flush_trace()` 的 `trace_steps` 里記 trace_id。
- 效益：admin-logs 頁可以直接跳轉到對應 agent trace。一天內做完。

**P2：Span/Event 語意分離 + 絕對時間戳**
- `ExecutionNode` 加 `kind: span|event`；`add_node()` 拆成 `add_span()` / `add_event(parent_span_id)`。
- 相對 offset 改為同時存絕對 `start_time`（UTC）——OTel 對齊的前置條件。
- 統一 web/LINE 兩份 persist 邏輯成一個 `persist_agent_trace()`。

**P3（核心決策點）：OTel 化 collector**
- 方案 A「翻譯層」：`AgentTraceCollector` 內部不動，新增 OTLP exporter 把 nodes 轉成 OTel spans（屬性名對齊 GenAI conventions）輸出。自有 UI 照舊，Langfuse 變成可選的第二視圖。
- 方案 B「原生替換」：collector 底層直接改用 `opentelemetry-sdk` 的 tracer，自有 DB 持久化改成一個自訂 SpanProcessor。
- 建議 A 先行（風險低、可逐步驗證），B 留待 A 穩定後評估。**這是要討論的第 1 個決策。**

**P4：Context propagation + 補盲區**
- 對 MCP server 呼叫與內部 HTTP 呼叫注入 `traceparent` header；MCP server 端（我們自己寫的那些）接收並延續 trace。
- arq worker 任務：入隊時把 trace context 序列化進 job payload，worker 端 restore——背景 LLM 呼叫從此有 trace。
- 效益：第一次能回答「這筆 OCR 成本是哪個對話觸發的」。

---

## 第二項｜CI Eval 閘門：prompt 改壞就擋 deploy

### 2A. 要學什麼

**promptfoo 的閘門模式**（要學的是模式，不是遷移過去——我們的斷言引擎已比它基本款強）：
- `promptfooconfig.yaml`：providers × prompts × tests(asserts) 的矩陣定義。
- 核心機制：`promptfoo eval` **失敗時 exit code 非 0** —— CI 閘門的全部本質就是這一行。
- GitHub Action：PR 上跑 eval、結果以 markdown 表格回貼 PR comment。
- 紅隊模組 `promptfoo redteam`：自動生成 injection/PII/越權攻擊案例（可對照我們的 `_security_base.yaml`，思路相同）。

**DeepEval 的 pytest 模式**（了解即可）：`assert_test(LLMTestCase(...), [FaithfulnessMetric(threshold=0.7)])`，指標學術化（G-Eval、RAGAS 系）。對我們的價值：它的 metric 定義文件寫得好，可以拿來校對我們 L1/L2/L3 judge prompt 的評分定義。

**LLM eval 在 CI 的三個工程難題（面試/提案都會被問）**：
1. **不確定性**：同一 case 兩次跑結果不同 → 解法是 N 次重跑取通過率（我們的 `validation_evaluator.py` 已經做了！）＋ P0 案例挑「行為型斷言」（tool_was_called、no_system_prompt_leak）而非「語氣型」。
2. **成本**：每個 PR 燒 judge token → 分層資料集（smoke 只跑 P0、全量夜跑）＋ 便宜 judge 模型。
3. **觸發時機**：我們的 prompt 不在 code 裡，在 DB（`bots.base_prompt`）→ CI 閘門只能防「程式碼與 prompt 模板改動」，**產品內編輯 prompt 要靠應用層閘門**（見 P3）。這是我們跟 promptfoo 情境的最大差異。

### 2B. 我們的現況

- 已有：`prompt_optimizer/` CLI（run/import/rollback/report）、32 種斷言（含資安）、golden dataset YAML（schema、P0/P1 priority、include 組合）、`validation_evaluator.py` N 次重跑通過率、`/estimate` 成本預檢、markdown report、rollback-to-iteration。
- 缺口：`.github/workflows/deploy-backend.yml` 完全沒接 eval；無 run A vs run B 比較視圖；無「從爛 trace 一鍵加入 dataset」；judge 從未對人工標註校準；UI 改 prompt 無任何攔截。

### 2C. 分階段方案

**P1：smoke dataset + gate 模式**
- 建 `datasets/smoke.yaml`：15–25 個 P0 案例，全部用行為型/確定型斷言（tool_was_called、contains_all、no_system_prompt_leak、refused_gracefully、latency_under、cost_under），加上 `_security_base.yaml`。
- CLI 加 `--gate` 旗標：P0 通過率 < 100% 或 P1 < 80% → exit 1；輸出簡短 markdown 摘要到 stdout。
- 加 `--budget` 上限（`CostStats` 已有基礎），超過即中止並失敗。

**P2：接進 GitHub Actions**
- 新 job：PR 觸發條件限定 paths（agent/prompt/RAG 相關目錄），跑 smoke + gate；judge 模型用便宜檔（決策點 2）。
- 結果回貼 PR comment（report markdown 已有，加一個貼 comment 的 step 即可）。
- 夜間排程跑全量 dataset，結果進 `prompt_opt_runs`，異常走既有 notification channel。
- 起步用 **warning 模式**（貼 comment 不擋 merge）跑兩週，斷言穩定後轉 blocking。**決策點 3。**

**P3：應用層閘門（我們獨有的需求）**
- 租戶在 UI 儲存 bot prompt 時：自動觸發該 bot 綁定的 smoke dataset `/validate`，P0 失敗 → 顯示失敗案例、要求二次確認或直接擋（分租戶等級設定）。
- 機制全部現成（`run_use_cases.py`、`/validate`、rollback），只差「儲存前置 hook」這一段接線。
- 順手補：`bots.base_prompt` 的手動編輯寫入 prompt 歷史表（現在只有 optimizer 改的有 `prompt_snapshot`）——這就是我們版的 prompt registry。

**P4：閉環（接第一項的 trace）**
- 爛 trace → dataset：trace 詳情頁加「加入評測集」按鈕，把該筆 `llm_input`/預期行為轉成 `eval_test_cases` 一列。生產流量從此回灌 golden dataset。
- run 比較視圖：兩個 run_id 的 case 級結果並排 diff（LangSmith 的殺手鐧，我們資料都在 `prompt_opt_runs.details`，缺的只是前端）。
- judge 校準：抽 50 筆 judge 打過分的回覆做人工標註，算相關性；不準就修 judge prompt。此後才能宣稱評分可信。

---

## 第三項｜PII 遮罩與保留期限：從技術債到合規賣點

> 三項中唯一「不做不行」的。現況拿去客戶環境部署即構成個資法風險：
> `react_agent_service.py:512` 把**完整訊息串全文未截斷**寫入 `agent_execution_traces.nodes`，無遮罩、無 TTL、無 opt-out。

### 3A. 要學什麼

**遮罩的三種做法與取捨**

| 做法 | 工具 | 取捨 |
|------|------|------|
| 規則式（regex + NER） | Microsoft **Presidio**（開源，analyzer + anonymizer，可自訂 recognizer） | 快、便宜、可離線；中文 NER 較弱，台灣格式要自寫 recognizer |
| LLM 遮罩 | 小模型過一遍 | 準但每筆 trace 加一次 LLM 成本與延遲，通常只用於高敏場景 |
| 確定性代換 | hash / tokenization（同一人名每次換成同一代號） | 保留可分析性（同一 email 的行為可串起來），適合搭配規則式 |

**Langfuse 的 masking hook 模式**（值得直接抄的架構思想）：遮罩函式註冊在 **client 端、ingestion 之前**——敏感資料離開應用邊界前就處理掉，觀測後端永遠看不到原文。對應到我們：遮罩要做在 `AgentTraceCollector` 這個單一咽喉點，不是做在查詢/顯示層。

**保留期限的業界分層**：原始 trace（含全文）短保留（30–90 天）→ 聚合統計（token/延遲/評分）長保留 → 計費帳（token_usage_records）不刪。刪除要可證明（審計記錄）。

**台灣個資法對照重點**：蒐集目的內使用、當事人刪除請求權（→ 需要 by user/conversation 的刪除路徑）、委外處理責任（→ 我們是客戶的受託處理者，客戶會拿這些問題審我們——**答得出來就是簽約優勢**）。

### 3B. 我們的現況

- `llm_input`/`llm_output` 全文入庫（`react_agent_service.py:512-515`）；`tool_output` 原始 JSON 入庫（`tool_trace_recorder.py`）；`guard_logs` 存 `user_message` 原文。
- 保留期限：`log_retention_policy_repository.py:70` **只刪 `request_logs`**；`agent_execution_traces`、`rag_evaluations`、`guard_logs`、`feedback` 全部無限增長。
- 附帶問題：`nodes` 是 `json` 非 `jsonb`（`agent_trace_model.py:37`），關鍵字搜尋 `::jsonb::text ILIKE` 全表掃描，全文入庫又是最大的膨脹來源——遮罩＋截斷會同時緩解效能問題。

### 3C. 分階段方案

**P1（一天級 quick win）：截斷 + 開關**
- `add_node()` 對 `llm_input`/`llm_output`/`tool_output` 統一上限（如各 4KB，保頭尾），超過標記 `truncated: true`。
- Bot 級設定 `trace_capture: full | truncated | metadata_only`（對照 GenAI conventions 的 opt-in 精神），預設 `truncated`。

**P2：遮罩層（咽喉點單點實作）**
- 在 collector 寫入路徑加 `mask(text) -> text` 管線；Presidio + 自訂台灣 recognizer：身分證字號（字母+9碼含檢查碼）、手機 09xx、市話、統編（8 碼含檢查邏輯）、信用卡（Luhn）、email、地址關鍵詞。
- 確定性代換格式如 `<PII:PHONE:a3f2>`（hash 後 4 碼），保留可串連性。
- `guard_logs.user_message` 與 feedback comment 同管線。
- 效能決策：同步遮罩（regex 級，微秒~毫秒）在寫入前做；若上 NER 則放進 fire-and-forget 持久化那一段（已是 async，不影響回應延遲）。

**P3：保留期限全表覆蓋**
- 擴充 `log_retention_policies`：per-table 天數（traces 90 / evaluations 保留分數刪 payload / guard_logs 180 / request_logs 沿用）。
- 排程用現有 arq worker 跑每日清理；每次清理寫審計行（表名、條件、刪除筆數、時間）。
- `token_usage_records` 明確標注「計費帳，不在清理範圍」。
- 個資請求路徑：`DELETE by conversation_id / line user id` 的 use case（feedback 已有 `/retention` 前例可仿）。

**P4：儲存層收尾**
- `nodes` 遷移 `json → jsonb` + GIN 索引（截斷後資料量已縮，遷移成本可控），關鍵字搜尋擺脫全表掃描。
- trace 匯出 API（JSON），支撐「客戶要拿走自己的資料」場景。

---

## 建議推進順序（三項交錯，先撿高價值低風險）

| 週次 | 動作 | 屬於 |
|------|------|------|
| W1 | 學習：OTel 概念 + 自架 Langfuse 練習；同時做 3-P1 截斷開關（quick win） | ①學 ③做 |
| W2 | 1-P1 request_id 關聯；建 smoke.yaml + `--gate`（2-P1） | ①② |
| W3 | 2-P2 GitHub Actions warning 模式上線；學 Presidio、寫台灣 recognizer 原型 | ②③ |
| W4 | 3-P2 遮罩層進 collector；1-P2 Span/Event 分離設計評審 | ③① |
| W5+ | 3-P3 保留期限；2-P3 應用層閘門；1-P3 OTel exporter（討論後定案） | 全部 |

---

## 實作前的討論決策清單

1. **OTel 化走翻譯層（A）還是原生替換（B）？**（建議 A 先行）
2. **CI judge 用哪個模型？** 成本/準確取捨；smoke 集刻意偏行為型斷言可以把 judge 依賴降到最低。
3. **CI 閘門何時從 warning 轉 blocking？**（建議跑兩週看誤擋率）
4. **遮罩時機：寫入前遮（合規最乾淨、除錯損真）vs 原文加密存 + 顯示層遮（保真、但金鑰管理成本）？**（建議寫入前遮 + `trace_capture` 開關給開發環境留後門）
5. **保留天數的預設值**：自用 vs 未來客戶部署是否要不同 profile？
6. **Langfuse 要不要真的常駐自架當第二視圖**，還是只當學習沙盒？（自有 React Flow DAG 是差異化資產，不建議棄守）

---

## 對 FDE 企劃的回饋（做完之後的說詞）

- 「追蹤系統相容 OTel GenAI semantic conventions」→ 企業客戶的採購檢核表直接打勾。
- 「prompt 迴歸自動擋版」→ 客戶 demo 的殺手級橋段。
- 「PII 遮罩＋保留策略＋個資刪除路徑內建」→ 委外處理者合規審查的現成答案，簽約差異化。
- 三項各自對應 `ai-fde-initiative` 企劃書第三節資產盤點的升級註記。
