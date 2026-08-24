# 康達盛通 POC 反饋修復計畫（問題 1-8 全項）

> 來源：2026-07-09 康達盛通 POC 測試反饋 8 題；2026-07-15 完成線上 trace 實證（見 memory `kangda-poc-feedback`）。
> 主管報告：`C:\Users\P10359945\Downloads\康達盛通-POC問題根因分析與解決方案.pdf`

## 總覽

| WP | 對應問題 | 類型 | 內容 | 工時 | 波次 |
|----|---------|------|------|------|------|
| A | 7 | **Bug fix（程式）** | DM 查詢 context 被同頁去重誤刪 | 1 天 | P0 |
| B | 3, 4 | Prompt＋小程式 | 連結輸出規則修正＋純文字格式約束＋LINE strip 安全網 | 1 天 | P0 |
| C | 1 短期 | 設定 | Input guard 模型 Sonnet→Haiku 降級 | 0.5 天 | P0 |
| H | 2 | 程式（小） | LINE 聯絡按鈕強制外部瀏覽器開啟（openExternalBrowser=1） | 0.5 天 | P0 |
| D | 6 | 設定＋小程式 | 意圖分流補強＋rag_query 綁 DM KB＋異體字正規化 | 1 天 | P1 |
| E | 5, 8 | 資料管線 | 重爬官方 FAQ 重建知識庫＋驗收題庫重測 | 1 天 | P1 |
| F | 1 中期 | 程式 | 管線並行化＋web 非串流 guard 重複執行修復 | 1.5~2 天 | P1 |
| G | — | Backlog | hybrid search／定期重爬＋自動汰換／parser 保留 href | 另估 | P2 |

依賴關係：A、B、C、H 互相獨立可並行；D、E、F 於第二波；E 依賴 B（先修 prompt 再重測才乾淨）。

---

## WP-A：DM 查詢 context 同頁去重誤刪（問題 7）— Bug Fix 工作流

**限界上下文**：RAG／Agent　**檔案**：`apps/backend/src/infrastructure/langgraph/dm_image_query_tool.py`

**根因**（已實證，trace `a4d62440`）：`invoke()` 的三層 dedup（by_doc:95 → storage_path:125 → page_number:130）原為圖片 carousel 防重複設計，但 context 組裝（:167-169）用的是 dedup 後的 `sources` → 同頁次高分 chunk（包大人 0.6337）從 LLM 可見上下文消失。

**修法**：context 與 sources 分離組裝——
- `context`：用 dedup **前**的檢索結果（`ordered` 或原始 top_k 結果）的 `content_snippet` 組裝，維持 `_truncate(500)` 與 top_k 上限
- `sources`（圖卡）：維持現有三層 dedup 不動

**Bug fix 工作流（不可省略）**：
1. 先寫 regression test（紅燈）：同一 document_id 兩個高分 chunk（模擬同頁幫寶適＋包大人）→ 斷言 context 包含兩者、sources 僅 1 張圖
2. 修復至綠燈
3. BDD：`apps/backend/tests/features/dm_image_query_dedup.feature`（同頁多商品場景）

**驗收**：線上重測「包大人尿布有優惠嗎」→ 回覆包含「包大人 買1送1」且 LINE 圖卡不重複。

---

## WP-B：連結輸出規則＋純文字格式（問題 3、4）

**限界上下文**：Agent／Platform

### B1. Prompt 修正（資料層，DB 更新）
- **問題 3**：`bot_workers.worker_prompt`（4 個 worker）與 `bots.bot_prompt` 中的「禁止在回覆中硬寫電話、URL 或連結」改為：
  「禁止自行編造或憑記憶輸出連結／電話；**知識庫檢索結果中出現的官方連結應原樣保留輸出**。轉真人按鈕與 DM 圖卡仍由系統自動顯示，不需重複描述。」
- **問題 4**：base prompt（`system_prompt_configs` ＋ 同步 `prompt_defaults.py` seed）加格式規範：
  「輸出純文字：禁止使用 `**`、`#`、`- ` 等 Markdown 符號；條列改用『・』。」
- 注意：live DB prompt 與 seed 檔已 drift（「禁止硬寫」字樣只在 DB），修改時**兩邊同步**，並將最終版本回寫 `scripts/seed_carrefour_workers_2026_05_13.sql`（或新增 dated seed 檔）。
- DB UPDATE 走 data migration 流程（preview → 執行 → verify → `_applied_migrations` 記錄）。

### B2. LINE 出口 Markdown strip 安全網（程式，TDD）
- **檔案**：`apps/backend/src/application/line/handle_webhook_use_case.py`（reply 前）＋新 util（`src/domain/platform/` 或 `src/application/line/_text_format.py`）
- strip 規則：`**bold**`→`bold`、行首 `#`／`- `→`・`，保留 URL 原樣
- 單元測試先行（含「不誤傷含星號的正常文字」案例）

**驗收**：重測「無法綁定會員卡」→ 回覆含 `carrefour.com.tw/carrefourapp` 連結；「如何成為 VIP」→ 無 `**` 符號。

---

## WP-C：Input guard 模型降級（問題 1 短期）

**類型**：純設定，無程式變更。

- `guard_rules_configs.llm_guard_model`：`anthropic:claude-sonnet-5` → `anthropic:claude-haiku-4-5`（維護頁調整，或 SQL data migration 留紀錄）
- 程式預設本就是 Haiku（`prompt_guard_service.py:413` `DEFAULT_GUARD_MODEL`），亦可清空欄位回退預設
- ⚠️ LINE「載入中」動畫**已上線**（`handle_webhook_use_case.py:331`，20 秒）— 無需開發，報告中此項視為已完成

**驗收**：調整前後各抽 10 筆 LINE trace 比較 `total_ms`，預期節點外耗時下降 0.5~1.5 秒；抽測 guard 攔截案例確認防護仍有效。

---

## WP-H：LINE 聯絡按鈕強制外部瀏覽器（問題 2）

**限界上下文**：Agent（LINE 通路）　**檔案**：`apps/backend/src/infrastructure/line/flex_contact_builder.py`

**根因（2026-07-15 客戶補充釐清）**：轉真人按鈕有正常出現與觸發，但按鈕 URI 在 **Android 的 LINE 內建瀏覽器（in-app WebView）**中開啟客服頁（tototalk 網路電話），WebView **不會彈出電話／麥克風授權視窗** → 網路電話卡住無法接通。非功能缺口，是 WebView 相容性問題。

**修法**：LINE URI action 官方支援 `openExternalBrowser=1` 查詢參數 — 加在 URL 上即強制以外部瀏覽器（Chrome／Safari）開啟，外部瀏覽器會正常詢問授權。

- `build_contact_flex()` 中 `contact_type == "url"` 時，對 `action_uri` 附加 `openExternalBrowser=1`（需處理既有 query string 的 `?`／`&` 拼接，用 `urllib.parse` 不要字串硬接）
- **範圍僅聯絡按鈕**：DM 圖卡（`flex_image_carousel_builder.py`）開啟的是圖片，無授權需求，留在 LINE 內體驗較佳，不動
- TDD：單元測試覆蓋「無 query」「已有 query」「tel: 型別不附加」三案例

**驗收**：Android 實機 LINE 點「轉接真人客服」按鈕 → 跳外部瀏覽器 → 網路電話授權彈窗正常出現、可接通。（iOS 一併回歸測試）

---

## WP-D：意圖分流＋KB 綁定＋異體字（問題 6）

**限界上下文**：Agent／RAG

### D1. 意圖分流補強（設定）
- `bot_workers` 的「商品查詢」worker description 補明確觸發詞：活動、檔期、周年慶、促銷、優惠、DM
- 實證中該題**無分流節點**（落 bot 預設模式）→ 一併檢查 intent classifier 對「無匹配」的 fallback 行為是否合理

### D2. rag_query 綁 DM KB（設定）
- bot 預設模式的 `rag_query` 目前只搜 FAQ KB → 用既有 per-tool KB binding（`Bot.tool_configs["rag_query"].kb_ids`，commit `8b9f438`）加入 DM KB（`559538a4`），或調整 bot 全域 KB 綁定。雙保險：即使分流失手也搜得到。

### D3. 查詢異體字正規化（程式，TDD）
- **檔案落點**：`apps/backend/src/application/rag/query_rag_use_case.py` 檢索前處理（embed 之前對 query 正規化）
- 對照表起步：週↔周、臺↔台、（可擴充）；正規化只影響 embedding 輸入，不改使用者原文
- 單元測試先行；Domain 層放對照表純函式，Application 層呼叫

**驗收**：重測「請問家速配週年慶有什麼活動」→ 回出「4周年慶：滿$399×4次贈$100折價券×2（2025/04/01-04/30）」；trace 確認分流到「商品查詢」或 rag_query 命中 DM KB。

---

## WP-E：重爬官方 FAQ 重建知識庫（問題 5、8）

**限界上下文**：Knowledge

1. **重爬**：基於既有 `scripts/scrape-carrefour-urls.cjs` 重跑／擴充，重新產出 `scripts/carrefour-faq-data.json`（含最新門市清單 81 家、官方新增條目如實名制）
2. **汰換**：刪除舊 FAQ 文件（既有 cascade 機制會清子頁與 Milvus chunks，commit `13d4306`）→ 重新匯入
3. **驗收題庫**：康達盛通 8 題 ＋ 既有 eval dataset 批次重測（`eval_datasets` 機制），確認無回歸
4. 若重爬後官方仍無「實名制」內容 → 回報並請康達盛通確認資訊來源（此為唯一可能需要客戶的分支）

**驗收**：「板橋店有沒有理髮店」→ 81 家版本資訊；「APP 實名制」→ 有答案（或確認官方無此內容）。

**依賴**：建議在 WP-B prompt 修正後執行，重測結果才乾淨。

---

## WP-F：管線並行化＋guard 重複執行修復（問題 1 中期）

**限界上下文**：Agent

### F1. web 非串流路徑 guard 雙重執行 Bug（先做，無爭議）
- **根因**：`send_message_use_case.py` 非串流 `execute`（:721 check_input／:818 check_output）與 `GuardedAgentService.process_message`（:70／:105）各跑一次 → input/output guard 各兩次
- Bug fix 工作流：regression test（斷言單次請求 guard 只執行一次）→ 移除其中一層（建議保留 GuardedAgentService 咽喉點，移除 use case 內重複呼叫，與 commit `24170fe` 的 Decorator 設計一致）

### F2. LINE 路徑 intent 分類與 input guard 並行化（⚠️ 有設計決策點）
- **衝突**：commit `8868ddb` 特意把 guard 提前到 intent classifier 之前（classifier 也餵 user message 給 LLM，防 injection 先污染）。並行化會讓 classifier 在 guard 判定前收到原文，**違反該安全契約**。
- **建議方案**：`asyncio.gather(guard, classify)` 並行執行，但 classifier 結果**僅在 guard pass 後採用**；guard block 時丟棄 classify 結果。風險面：injection 文本會進 classifier LLM 一次，但其輸出僅為 worker 選擇（enum），無自由文本外洩面。預期省 0.5~1.5 秒。
- **此決策需 Larry 確認後才實作**；若不接受風險則 F2 取消，僅保留 F1。

**驗收**：LINE trace `total_ms` 中位數較 WP-C 後再降；非串流路徑 guard 呼叫次數 = 1（以 log／trace 佐證）。

---

## WP-G：P2 Backlog（本計畫僅登記，另行排程）

- Hybrid search（BM25／keyword ＋向量混合）— 根治精確詞檢索弱點（5~8 天）
- FAQ 定期重爬排程＋同名條目自動汰換 — 根治資料過期（3~5 天，含 WP-E 腳本產品化）
- 文件解析器保留超連結（HTML/DOCX/XLSX/PDF href）（2~3 天）
- tel: 直撥／phone 型別（既有 roadmap 預留；WP-H 若能滿足客戶則可降級）

---

## 執行順序與 Stage 0

```
第一波（並行）：WP-A ─┐
                WP-B ─┼─→ 完成後通知客戶重測 P0 五題（2/3/4/7 + 延遲體感）
                WP-C ─┤
                WP-H ─┘（問題 2 需 Android 實機驗證）
第二波：       WP-D ─┐
                WP-E ─┼─→（E 依賴 B）批次重測 8 題全量
                WP-F ─┘（F2 需先確認設計決策）
```

**GitHub Issues（計畫確認後建立）**：
- Issue：WP-A（label: bug）
- Issue：WP-B＋C（label: enhancement，prompt/config 波）
- Issue：WP-H（label: bug，LINE WebView 相容）
- Issue：WP-D（label: enhancement）
- Issue：WP-E（label: enhancement，資料重建）
- Issue：WP-F（label: bug＋refactor）
- 每個 issue 含 Sub-tasks checkbox＋Acceptance Criteria；commit 帶 `Refs #N`；完成後同步 `SPRINT_TODOLIST.md`
