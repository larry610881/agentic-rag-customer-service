# 通路對等規範（Channel Parity）

> 本規範固化 2026-08-20 的架構診斷教訓：LINE 被實作成一條 1,123 行的平行管線
> （`application/line/handle_webhook_use_case.py`），與 web/widget 的
> `application/agent/send_message_use_case.py`（1,440 行）重複實作 guard、意圖分類、
> trace、history，並已多次 drift 出實際事故——prompt guard 曾只有 web 有
> （7/1 家樂福角色劫持事件）、快速道（Issue #50）只有 LINE 有、LINE 完全沒有 eval、
> trace 持久化寫了兩份。根因：**做了 DDD 分層，沒做「功能 × 通路」的分離**。

## 核心原則

> **通路（web / widget / LINE / 未來任何通路）是 interfaces 層的轉接器，不是限界上下文。**
> **功能屬於對話管線，管線邏輯只能存在一份，活在所有通路共用的 application 層 service。**

## 紅線

### 1. 對話管線邏輯禁止按通路實作（CRITICAL）

以下「管線步驟」的邏輯**只准有一份實作**，由所有通路共同呼叫：

- prompt guard（輸入/輸出防護）
- 意圖分類 / worker 路由 / 快速道（direct_retrieval）判定
- agent 執行（ReAct / supervisor / meta_supervisor）
- RAG 檢索與 rerank 決策
- trace 收集與持久化
- token usage 記帳
- LLM 品質評估（eval）
- 對話歷史組裝

在 `application/line/`（或未來任何通路目錄）內新增/修改上述邏輯 = **CRITICAL 違規**。
正確做法：改共用 service，通路端只接收結果。

### 2. 通路目錄只准放 I/O 適配

`application/line/` 與各通路 router 只准包含：

- 通路協定處理（webhook 簽章、reply token、SSE 事件封裝）
- 訊息格式翻譯（中性事件 → flex 圖卡 / SSE token / widget 訊息）
- 通路特有的回覆組裝（LINE 聚合非串流、web 串流）

### 3. 通路判斷用能力旗標，不用通路名（HIGH）

管線程式碼中出現 `if channel == "line"` / `if source == "web"` 這類分支 = HIGH 違規。
改用能力描述：`supports_streaming`、`supports_rich_card`、`max_message_length` 等旗標，
由各通路轉接器宣告。新通路 = 新轉接器 + 一張能力表，管線零修改。

## 計畫與 Review 檢查項

1. **計畫階段（Stage 1）**：任何涉及對話管線的新功能，計畫必須包含「通路覆蓋聲明」
   ——預設 web/widget/LINE 全覆蓋；只做部分通路必須寫明理由與補齊計畫。
2. **BDD（Stage 2）**：管線行為的 `.feature` 必須可跨通路重用（scenario 不綁通路，
   或以 Scenario Outline 覆蓋各通路）。
3. **Code Review / ddd-checker**：diff 碰到管線步驟關鍵字（guard/intent/trace/usage/
   eval/direct_retrieval/history）卻只落在單一通路檔案 → 標記違規。
4. **驗收**：管線功能的驗收條件必須含「三通路行為一致」。

## 現存債務（絞殺者遷移，不可大爆炸重寫）

既有的兩條平行管線屬歷史債，依此順序逐步抽取共用 service（每步獨立可驗證、
家樂福 LINE 行為零回歸）：

1. 快速道抽取（`onboarding-and-bot-wizard-requirement-brief.md` 需求三，進行中）
2. trace 持久化統一（兩份 `_persist_agent_trace` 合一）
3. guard 呼叫點統一
4. eval 補上 LINE 通路（目前 LINE 每輪對話無品質評估）
5. usage 記帳路徑統一（含 full-review M12：SSE 中斷漏記——記帳移入
   `execute_stream` 產生 usage 當下即落帳，router 不再事後補記）
6. 長期記憶接上 LINE（full-review M21：`memory_enabled` 對 LINE 靜默無效；
   LINE user_id 穩定、本是 memory 最適用通路。先抽共用 memory service 再由
   LINE 轉接器呼叫，禁止在 `application/line/` 內複製 load/extract 邏輯）
7. 閘門 replay 通路保真（full-review M22：回放 LINE 流量走 web 影子管線，
   結果已標注 `pipeline_approximation: "web"`；管線統一後以能力旗標模擬來源通路）
8. 最終：`ConversationTurnPipeline` 共用管線 + 中性事件流輸出

在債務清完之前，任何觸碰兩條 use case 的修改，都必須自問：
**「這段邏輯是不是應該趁這次抽成共用？」**——順手還債優先於再堆一層。
