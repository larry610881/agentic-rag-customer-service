# 需求 Brief：新手引導流程 × Bot 建置精靈 × 快速道通用化 × 管線通路統一

> 給執行本需求的 Claude session：這是一份**需求書＋設計決策紀錄**，由規劃 session 與 Larry 討論後定案。
> 你的任務分兩階段：**先產出規劃書（spec）與待決清單，經 Larry 確認後才開始開發。**
> 相關文件：`docs/prompt-gate-requirement-brief.md`（prompt 發布閘門，可能已在進行或已完成）——本需求與它有一個關鍵整合點（見 2.6），規劃時必須對齊，若該需求已開發完成則直接串接其產出。
>
> 商業脈絡：這兩個功能是對外銷售的核心賣點（sales deck 的「十分鐘開站」與「Bot 建置精靈」頁），目標使用者是**不懂技術的新手客戶**，且精靈要能支撐業務「現場用客戶自己的文件 demo」的場景——體驗流暢度與速度是硬需求。

---

## 需求一：新手引導流程（In-Product Onboarding）

### 1.1 目標

新租戶首次登入後，**不需要文件、不需要 IT 人員陪同**，被引導完成從零到第一個可用機器人的最短路徑。文件與影片是補充，不是主體——引導必須內建在產品裡。

### 1.2 規格

- **首次登入 checklist**（四步）：建立知識庫 → 上傳文件 → 測試提問 → 發布 widget。
  - 每步完成狀態自動偵測（不是手動打勾）：例如「上傳文件」在該租戶第一份文件索引完成時自動達成。
  - 進度持久化（per tenant），可中斷續走，可手動收合/永久關閉。
  - 入口：dashboard 常駐引導卡片，完成全部後自動收斂為「完成」狀態並淡出。
- **步驟級引導提示**：每步進入對應頁面時的 coach mark／提示框（指出該按哪裡、貼一句範例輸入），只在該步未完成時出現。
- **與精靈的關係**：checklist 第一步旁提供「讓 AI 顧問幫我建（推薦）」入口 → 走需求二的精靈流程；精靈完成即等於 checklist 前三步一次達成。手動路徑保留。
- **啟用指標（規劃書中須定義埋點）**：租戶從註冊到「第一次成功問答」與「第一次發布 widget」的轉化率與耗時——這是本功能的成效 KPI，之後也是 sales 素材。

### 1.3 邊界

- v1 只做 web admin 的引導；widget/LINE 端不在範圍。
- 不做影片教學、不做互動式 demo 沙盒（有精靈就不需要）。

---

## 需求二：Bot 建置精靈（AI 開站顧問）

### 2.1 目標

客戶提供文件後，一個 agent 自動分析內容、簡短訪談，**直接生成一個可測試的 draft 機器人**——含 prompt、檢索建議、防護建議、以及一組從文件抽出的測試題。把「開站」從專業工作變成十分鐘體驗。

### 2.2 流程（定案，照此規劃）

```
① 客戶上傳文件（走既有 KB pipeline：解析、索引、自動分類）
② 內容分析：文件主題分佈、語言、文件類型（FAQ/手冊/規章/商品）
③ 精靈訪談（對話式，見 2.3）：行業、機器人用途、語氣偏好＋需求探詢
   ├─ 同步進行：整合機會偵測（見 2.7）——從訪談內容與知識庫分析中
   │   辨識超出 RAG 問答範圍的需求（系統串接、skill/MCP、客製 agent）
④ 自動產出五件套：
   a. base_prompt 草稿（複用 prompt_optimizer 的 LLM 改寫引擎，不重寫）
   b. 檢索模式組合建議（依內容型態：FAQ 型偏精準比對、手冊型偏語意+rerank 等）
      ＋快速道（direct_retrieval，Issue #50）啟用建議：FAQ 型內容佔比高的
      worker 建議開啟，附延遲/成本效益說明（依快速道通用化進度，見該機制評估）
   c. guardrail 建議（依行業：金融加個資敏感詞、電商加退換貨邊界等）
   d. 從文件自動抽 15–20 題 golden Q&A（含預期答案要點與來源出處）
   e. agent 架構建議：單 agent（react）vs 多 agent（supervisor / meta_supervisor，
      皆為既有 agent_mode）——依訪談蒐集的需求複雜度評估：知識庫是否跨多領域、
      是否需要多工具/多部門分工、量級與延遲容忍度；建議附一句白話理由
      （「你的需求單一 agent 就夠，不用為了多 agent 多花成本」也是有價值的建議，
      呼應「先診斷、不硬上」原則）
⑤ 生成 draft bot（含上述配置），導向 Studio 讓客戶立刻試問
⑥ 客戶測試後可：採用（發布）／調整任一件套後重試／放棄
```

### 2.3 訪談互動形式（已定案：對話式為預設）

- **v1 即做對話式訪談**——這是「AI 顧問」體驗的核心，不是 v2 選配。
- 對話式≠無結構：精靈帶著**固定的訪談目標清單**進行（行業、用途、語氣、使用對象、預期量級、**「除了問答，你還希望它能幫你做什麼？」**），逐項蒐集、可追問、蒐集齊即收斂——實作上是「目標驅動的對話狀態機」，不是自由聊天。
- 離題處理：溫和拉回訪談目標；聊出範圍外的需求正是 2.7 要捕捉的訊號，**記錄下來，不丟棄**。
- 訪談內容須結合 ② 的知識庫分析結果提問（例：「我看到文件裡有退換貨規章，機器人需要處理退換貨諮詢嗎？」）——讓客戶感覺精靈「讀過他的文件」，這是體驗的關鍵時刻。
- 保留「快速模式」跳過訪談（全用預設值），供趕時間的 demo 場景。

### 2.4 golden Q&A 自動抽題（本功能的技術核心）

- 從已索引的 chunk 抽題：每題含 `question`、`expected_points`（答案要點，非全文）、`source_chunk 引用`、建議斷言（複用 `prompt_optimizer/assertions.py` 的既有斷言型別，如 `contains_any`、`has_citations`）。
- 題目分佈要求：覆蓋主題分類（不可全擠在同一份文件）、含 2–3 題「文件裡沒有的問題」（測拒答行為，斷言 `refused_gracefully`）。
- 產出直接寫入既有 `eval_datasets` / `eval_test_cases`（walk 既有 CRUD use case，不繞過）並綁定該 bot。
- 抽題品質規劃書須設計自檢機制（例如抽完自跑一輪、剔除連源文件都答不出的題）。

### 2.5 功能開關與用量分流（與 prompt-gate brief 同規則）

- 平台層 per-tenant 開關（admin 控制哪些租戶可用精靈）；system 帳號預設開啟。
- Token 用量：新增 `UsageCategory`（建議 `bot_wizard`），走 `record_usage_use_case` 帳本，歸因 tenant/bot；執行前 `/estimate` 成本預檢；每租戶每日次數上限（防濫用，demo 場景要可由 admin 臨時調高）。

### 2.6 與 prompt 閘門的整合點（關鍵）

- 精靈產出的 golden Q&A **正好滿足閘門「須先綁定題集才能啟用」的前置條件**——精靈完成時，若該租戶的閘門功能已開放，主動提示「已為你準備好品質防護題組，是否啟用發布閘門？」。
- 精靈產出的 base_prompt 若閘門已上線，應以 draft 版本進入 prompt 版本狀態機，而非直接寫 `bots.base_prompt`。
- 規劃書中須明確處理兩種時序：閘門先完成／精靈先完成（精靈不得對閘門產生硬依賴，閘門缺席時 fallback 直寫）。

### 2.7 整合機會偵測與商機轉介（商業上的關鍵功能）

精靈在訪談與內容分析過程中，主動辨識**超出 RAG 問答能力範圍的需求**，並轉化為對 IT 單位（本公司）的客製開發商機：

- **偵測訊號來源**：
  - 訪談語句：「希望它能查訂單／幫客人下單／同步到我們的 ERP／自動開工單」→ 系統串接需求。
  - 知識庫內容：文件中出現表單流程、審批流程、對外系統名稱 → 潛在自動化場景。
- **產出形式：「進階能力建議卡」**——精靈完成時，除五件套外額外呈現 0–N 張建議卡，每張含：
  - 偵測到的需求描述（引用客戶原話或文件出處）
  - 可行的實現方式分類：`現成 skill 串接` / `MCP 工具串接` / `需客製開發（agent／系統整合）`
  - CTA：「聯繫我們的顧問評估」按鈕
- **商機轉介機制（lead pipeline）**：
  - 客戶按下 CTA → 記錄 lead：`tenant_id, bot_id, 需求描述, 分類, 來源(訪談/文件), 狀態(new/contacted/closed), created_at`。
  - 走既有 `notification_channels` 通知內部（業務/IT 單位收件人可設定）。
  - Admin 後台需有 lead 列表頁（平台管理者視角，跨租戶）。
  - **就算客戶不按 CTA，偵測到的機會也要留存**（狀態標 `detected`，不通知客戶端）——供業務事後跟進判斷。
- **語氣紅線**：建議卡是「我們注意到你可能還需要…」的顧問語氣，一次呈現不超過 3 張、不重複推播——精靈的本體價值是幫客戶開站，商機偵測是自然副產物；過度推銷會毀掉信任，這條在 UI 文案審查時嚴格把關。
- **與 FDE 服務線的關係（背景）**：這些 lead 正是「AI Agent 客製開發」與「AI 轉型陪跑」服務的入口，是產品帶服務的商業模式核心，優先級不低於五件套。

### 2.8 效能預算（demo 硬需求）

- 業務現場 demo 情境：20 份以內文件 → 從上傳到 draft bot 可測試 **≤ 10 分鐘**；訪談後的五件套生成 **≤ 90 秒**（可分段串流呈現進度，體感優先）。
- 規劃書中給出各段耗時預估與並行化方案（抽題與 prompt 生成可並行）。

---

## 需求三：快速道（direct_retrieval）通用化

> 背景：Issue #50/#51 的快速道（意圖命中 → 跳過 ReAct → 直接檢索 → 門檻判定 → 單次生成，失敗自動升級 ReAct）原本**只實作在 LINE 路徑**，開關 `bot_workers.direct_retrieval` 只能下 SQL 開。
> 原則（Larry 定案）：**所有機制、所有渠道（web/widget/LINE）都必須實作**；機制必須是可設置的，不是程式寫死。
>
> **2026-09-02 狀態更新（Issue #61 / #66）**：
> - 3.1-1、3.1-2 已完成：`application/agent/direct_retrieval_service.py` 為共用服務，web/widget/LINE 共同呼叫；生成留在各通路（web 串流補發 sources 事件、LINE 圖卡）。
> - 3.1-3 已完成：worker CRUD API 與後台表單有 `direct_retrieval` 開關。
> - 3.1-4 定案為**兩層 profile**（見 3.3），不再只是評估。
> - 快速道 profile 固定 raw-only（不做 rewrite / HyDE）；rerank 由 bot.mode 決定。
> - 家樂福 POC 若不續做，本需求仍成立（快速道是「快速 bot」的引擎、精靈的落地欄位、需求四第 1 步）；僅家樂福專用的 DM 圖卡工具降為選配、`seed_carrefour_workers` 不再維護、驗收改用示範商店題組。

### 3.1 規格

1. **抽共用 service** ✅：檢索＋門檻判定＋fast_prompt 組裝＋escalated 升級語意＋來源回填，web/widget/LINE 共同呼叫（plan / generate 分離：服務只回「怎麼生成」，生成由通路呼叫自己的 agent_service）。
2. **DM 圖卡等通路特化行為**保留在各通路的呼叫端 ✅。
3. **設定面補全** ✅：worker CRUD schema 與前端表單有 `direct_retrieval` 開關（文案：「常見問題直答，複雜問題自動升級完整推理」）；快速道 trace 節點（direct_retrieval / escalated）三通路皆進 AgentTraceCollector。
4. **bot 層級 profile**（Issue #66，取代原「評估項」）：見 3.3。
5. **與精靈串接**：精靈五件套 b 項改為「先建議 bot.mode，再建議個別 worker 例外」。

### 3.2 驗收

- 同一 worker 開啟 direct_retrieval 後，web/widget/LINE 三通路行為一致（含升級 fallback 與 trace 記錄）✅（`direct_retrieval_shared.feature`）。
- 開關全程可在 admin UI 操作，不需 SQL ✅（Issue #66）。
- 既有 LINE 行為零回歸：既有測試全綠；線上實測待示範商店資料重建。

### 3.3 快速 / 深度兩層 profile（2026-09-02 定案）

| bot.mode | worker 未開 direct_retrieval | worker 開 direct_retrieval |
|---|---|---|
| `fast` | 一律快速道（沒有 worker 也走） | 快速道；rerank / rewrite / HyDE 一律關 |
| `deep`（預設） | 完整 ReAct | 快速道；rerank 依 bot / worker 設定 |
| `kb`（Issue #70，知識庫問答） | 檢索命中 → 單次生成、無任何工具；未命中 → `miss_reply`（不升級 ReAct）；工具 / 記憶 / 摘要 / 評估全關，不呼叫意圖分類 | 同左（kb 不分流，worker 設定不生效） |

- `fast` 的升級語意：檢索未過門檻仍升級 ReAct，但 `max_tool_calls` 上限 2、rerank / rewrite / HyDE 關；**升級率是 KPI**（高 = 知識庫覆蓋不足，補資料而非放寬時間）。
- 意圖分類保留（同時提供改寫查詢與攻擊判定）；只有一個 worker 時跳過選路但保留清洗（待做）。
- `mode` 進設定快照白名單與執行時指紋（`EffectiveConfig.extra.mode`）。
- `kb` 的成本上限：每題恰好 1 次 embedding + 1 次 LLM 呼叫（json 格式驗證失敗時最多再 1 次重試）；trace 無 `intent_classify` / `tool_call` 節點，未命中記 `kb_miss`（含 top_score / threshold）。回覆的 `structured_content.retrieval` 帶 `{top_score, chunk_count, threshold, miss}`。
- `output_format`（text | plain_text | json）與 `miss_reply`、`output_schema`、`output_text_field` 不限 kb，三通路共用同一份 `application/agent/output_format.py` 決策（channel-parity）。
- 環境變數 `FAST_LANE_ALLOW_RERANK` 已移除（違反「可設置、不寫死」）。

## 需求四：對話管線通路統一（絞殺者遷移，獨立 phase）

> 背景與規範：見 `.claude/rules/channel-parity.md`（2026-08-20 新增）。診斷結論：
> web/widget 走 `SendMessageUseCase`（1,440 行）、LINE 走 `HandleWebhookUseCase`
> （1,123 行），兩條平行管線重複實作 guard/意圖/trace/history，且已不對稱
> （LINE 無 eval、usage 記帳路徑不同、快速道只在 LINE、guard 曾只在 web）。
> 原則（Larry 定案）：功能與通路分離——管線邏輯一份、通路只做 I/O 轉接。

### 4.1 目標架構

- Application 層唯一一條 `ConversationTurnPipeline`：guard → 意圖/路由 → 快速道判定 →
  agent → trace → usage → eval，輸出**中性事件流**（token、來源、圖卡、轉真人…）。
- Interfaces 層通路轉接器（agent_router / widget_router / line_webhook_router）：
  輸入端做協定解析與正規化，輸出端把中性事件翻成通路格式（SSE 串流 / LINE 聚合+flex 圖卡）。
- 通路差異以**能力旗標**表達（supports_streaming、supports_rich_card 等），
  管線內禁止 `if channel == ...` 分支。

### 4.2 遷移順序（每步獨立交付、可驗證，禁止大爆炸重寫）

> **2026-09-02 狀態更新**：第 1 步完成（Issue #61）；第 4 步需求已變——線上每輪 LLM 自評已下線（Issue #59，從未成功寫入），改為「營運訊號（p50/p90、升級率、轉真人率、guard 攔截）＋離線 gate 回放三通路一致」（Issue #63）。新增待遷移項：EffectiveConfig 組裝（#60 兩邊各一份）、長期記憶接 LINE（M21）、閘門回放通路保真（M22）。

1. 快速道抽共用 service ✅（＝需求三，Issue #61）
2. trace 持久化統一（兩份 `_persist_agent_trace` 合一；#57 已讓節點一致、config_hash 各寫一次）
3. guard 呼叫點統一（web 先 guard 再分類、LINE 並行——分類器先看到攻擊原文，紅隊視角的實質差異）
4. ~~eval 補上 LINE 通路~~ → 營運訊號與離線回放三通路一致（Issue #63）
5. usage 記帳路徑統一（LINE 仍無 config_version_id；SSE 中斷漏記 M12）
6. EffectiveConfig 組裝、長期記憶（M21）、閘門回放保真（M22）併入共用管線
7. 收斂為 ConversationTurnPipeline + 中性事件流

### 4.3 驗收

- 每步遷移後：全量測試綠、家樂福 LINE 行為零回歸、web/widget 無回歸。
- 全部完成後：ddd-checker 的通路對等掃描（CRITICAL 第 4 項）零違規；
  兩條 use case 縮減為薄轉接器（各 < 300 行為目標）。
- 規劃書中須含：每步的抽取範圍、受影響測試清單、風險與回滾方式。

---

## 三、既有零件對照（先讀，不要重造）

| 零件 | 位置 |
|------|------|
| KB pipeline / 自動分類 | `application/knowledge/`、UsageCategory 已有 `auto_classification` |
| Prompt 改寫引擎 | `apps/backend/prompt_optimizer/mutator.py` |
| 斷言型別 | `apps/backend/prompt_optimizer/assertions.py` |
| 題集 CRUD | `application/eval_dataset/`、`interfaces/api/eval_dataset_router.py` |
| 檢索模式 | `application/rag/query_rag_use_case.py`（multi-mode + rerank） |
| Guardrail 設定 | `guard_rules_configs` + `application/security/prompt_guard_service.py` |
| 用量帳本 / 預檢 | `record_usage_use_case.py`、`/estimate` |
| Studio 即測 | `features/bot/`（live-trace-graph 所在的 Bot Studio） |
| 背景任務 | arq worker（精靈的分析/抽題應走 worker，避免佔用請求） |

## 四、工程約束（repo 既有紀律）

- DDD 四層；migration 手寫 SQL；Pure ASGI middleware；觀測/記帳 fail-open；pytest + pytest-bdd 覆蓋；新表帶 `tenant_id` 走既有 scoping。
- 精靈屬長流程任務：狀態機（分析中/待訪談/生成中/完成/失敗）須可查詢、可斷點續跑、失敗可重試單段。

## 五、待決清單（規劃書逐項給建議，經 Larry 確認後實作）

1. 商機 lead 的通知收件流程：通知誰（業務單位信箱？平台 admin？）、用哪個 channel、要不要 SLA 提醒（lead 三天未 contacted 再提醒）。
2. 抽題數量與品質門檻（15–20 題是否含拒答題在內；自檢剔題的標準）。
3. 精靈使用哪個檔次的模型（訪談對話/分析/抽題/prompt 生成可用不同檔）。
4. 既有 bot 可否重跑精靈（重新建議配置）還是僅限新 bot？
5. `bot_wizard` 用量計費：租戶配額 vs 平台吸收（demo 場景建議平台吸收）。
6. 新手引導與精靈的 UI 主動線：精靈是否為 onboarding 的預設路徑（手動為次要）？
7. 多語言：v1 是否僅繁中文件？
8. 「快速模式」（跳過訪談）開放給所有租戶，還是僅內部 demo 帳號？
9. 整合機會偵測的訊號分類初版清單（哪些關鍵詞/意圖對映到 skill/MCP/客製開發三類）——需 Larry 參與定義。

## 六、交付順序

**階段一（先做，產出後停下等確認）**：規劃書一份，含——四需求的資料模型/狀態機、API 端點、UI 流程圖（onboarding checklist 與精靈五步的線框描述）、抽題演算法設計、快速道共用 service 的抽取設計（含 web/LINE 呼叫端差異分析）、與 prompt-gate 的整合時序、效能預算分析、埋點/KPI 定義、測試計畫、phase 切分、第五節待決清單建議方案。

**階段二（確認後）**：依規劃書分 phase 實作。建議 phase 順序：**需求三快速道通用化先做**（範圍最小、獨立、精靈的建議項依賴它，同時是需求四遷移的第 1 步）→ 精靈後端（分析+訪談狀態機+抽題+五件套）→ 商機偵測與 lead pipeline（與五件套同等優先）→ 精靈 UI → onboarding checklist（依賴最少，也可並行）→ 與閘門串接 → 需求四其餘遷移步驟（2–6，可與精靈開發交錯排程，規劃書中給建議）。
