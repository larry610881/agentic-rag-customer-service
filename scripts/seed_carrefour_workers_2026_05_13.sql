-- 家樂福subagent測試 bot — 新增「門市服務查詢」worker
-- 日期: 2026-05-13
-- 動機: trace b0b74e6c 顯示「機車換胎」query 被誤路由到「商品查詢」worker，
--       但商品查詢 worker 進去後沒查 FAQ，直接轉真人 → 兩階段判斷不一致。
--       根因：bot 缺「門市服務查詢」worker 涵蓋藥局/輪胎中心/機車中心/汽車
--       美容/百元理髮店/霜淇淋/inLove cafe/DM 全台範圍說明 這 8 條 FAQ chunks
--       的查詢職責。新增 worker 後 supervisor router 多一個可選類別，FAQ
--       semantic gap 類問題直接路由到此 worker，由 rag_query 從 FAQ KB 查詢。
--
-- 套用：dev-vm（2026-05-13 已套）
-- 後續：UPDATE 為依實際 FAQ chunks 內容精化 description + worker_prompt
--      （以 chunk 內容定義 router routing keyword + worker 行為紀律）
--
-- 此檔為配置變更紀錄（非 migration）— 不會自動套用，純 audit trail。
-- 若要重 seed bot 設定可手動執行此 script。
--
-- 相關：
--   - bot_id 2feba9a0-... = 家樂福subagent測試
--   - FAQ KB id b62f123f-... = 家樂福FAQ
--   - trace_id b0b74e6c-db05-4386-ab01-8e7aa5b607e6 = 原始問題 trace

-- ============================================================
-- Step 1: INSERT 新 worker（已套）
-- ============================================================
INSERT INTO bot_workers (
    id, bot_id, name, description, worker_prompt,
    temperature, max_tokens, max_tool_calls,
    enabled_mcp_ids, knowledge_base_ids, enabled_tools,
    sort_order, tool_configs, created_at, updated_at
) VALUES (
    gen_random_uuid(),
    '2feba9a0-47b0-49d2-94ee-494fde39d926',
    '門市服務查詢',
    '使用者問門市服務、設施、各分店是否有提供 X 服務（例：哪些門市有藥局、輪胎中心、機車中心、汽車美容、百元理髮店、加油站、寵物店、霜淇淋、inLove café）— 屬全台分店 FAQ 查詢',
    '你是家樂福分店服務顧問。任務：協助查詢各分店的服務設施與營業範圍。一律先呼叫 rag_query 從 FAQ 知識庫查詢，再依結果回答。若 FAQ 真的沒有相關資料才使用 transfer_to_human_agent。禁止編造分店清單，禁止用先驗知識直接拒答。',
    0.1, 1024, 5,
    '[]'::json,
    '["b62f123f-bd69-471d-bb5d-44d5ce8c6788"]'::json,
    '["rag_query", "transfer_to_human_agent"]'::json,
    0, '{}'::json, NOW(), NOW()
)
ON CONFLICT DO NOTHING;

-- ============================================================
-- Step 2: UPDATE 用實際 FAQ chunk 內容精化 description + prompt（已套）
-- 依「賣場服務與促銷資訊」category 8 條 chunks 實際內容調整：
--   1. DM 商品全台販售情況
--   2. 網站促銷活動範圍
--   3. 藥局服務分店（信東/丁丁）
--   4. 輪胎中心 + 機車中心（彰化）
--   5. 汽車美容服務分店
--   6. 霜淇淋販售分店（量販店限定）
--   7. 百元理髮店服務分店
--   8. inLove cafe 販售分店
-- ============================================================
UPDATE bot_workers SET
    description = '使用者詢問家樂福分店服務、設施、營業範圍。涵蓋：(1) 服務設施分店清單 — 藥局（信東/丁丁）、家樂福輪胎中心、家樂福機車中心、汽車美容、百元理髮店；(2) 特定商品/服務的販售門市 — 霜淇淋、inLove cafe；(3) DM/網站促銷的全台適用範圍說明。不處理商品價格促銷詢價、退貨退款、會員權益、錢包儲值、APP 使用。',
    worker_prompt = E'你是家樂福分店服務顧問。任務：回答使用者關於各分店服務設施與營業範圍的問題（藥局、輪胎中心、機車中心、汽車美容、百元理髮店、霜淇淋販售、inLove cafe 販售、DM/網站促銷的全台範圍說明等）。\n\n## 必須遵守的流程\n1. 收到使用者問題 → 一律先呼叫 rag_query 從 FAQ 知識庫查詢\n2. 用 rag_query 回傳的內容作為回答唯一依據\n3. 若 rag_query 真的查無資料 → 使用 transfer_to_human_agent 轉真人\n\n## 回答風格\n- 完整呈現分店清單：FAQ 包含完整地區/店名清單時，原樣保留呈現，不要省略或縮減。\n- 跨頁延伸資訊必須提及：FAQ 常見「主答案 + 附帶資訊」結構（例：「家樂福輪胎中心 20 家... 另有家樂福機車中心 1 家：彰化」），附帶資訊不可遺漏。\n- 跨輪追問：使用者用「也是嗎」「那 X 呢」「也有 X 嗎」等代詞繼續追問時，視為同類問題繼續呼叫 rag_query，不要當作離題。\n- 附註原樣保留：FAQ 有「商家資訊將持續更新，詳細資訊請與各分店聯絡」這類提醒，原樣保留。\n\n## 禁止事項\n- 禁止編造任何分店名稱、清單或服務內容\n- 禁止用先驗知識直接拒答（一定要先 rag_query）\n- 不處理商品價格、促銷詢價、退貨退款、會員權益、錢包儲值、APP 使用問題（這些由其他 worker 處理）',
    updated_at = NOW()
WHERE name = '門市服務查詢'
  AND bot_id = '2feba9a0-47b0-49d2-94ee-494fde39d926';
