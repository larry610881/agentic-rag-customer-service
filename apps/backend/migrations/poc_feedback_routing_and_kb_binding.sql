-- 康達盛通 POC 問題 6（家速配周年慶查不到）— 意圖分流補強 + rag_query 綁 DM KB
-- Plan: .claude/plans/poc-feedback-fix-plan.md WP-D1 / WP-D2
-- 目標環境：dev-vm；影響範圍：LINE bot「家樂福subagent測試」(2feba9a0)
-- 根因（trace 08d19c40 實證）：「請為家速配週年慶有什麼活動」未分流到商品查詢
-- worker（description 無「活動」觸發詞），落 bot 預設後 rag_query 只綁 FAQ KB → 搜錯庫

-- 1. D1：商品查詢 worker description 補活動/檔期觸發詞（冪等，預期 1 row）
UPDATE bot_workers SET description = description ||
  '；問活動、優惠活動、促銷活動、檔期、周年慶/週年慶、節慶檔期（例：周年慶有什麼活動、家速配活動、母親節檔期）'
WHERE bot_id = '2feba9a0-47b0-49d2-94ee-494fde39d926'
  AND name = '商品查詢'
  AND description NOT LIKE '%周年慶%';

-- 2. D2：bot 預設模式 rag_query 加綁 DM KB（雙保險 — 即使分流失手也搜得到）
--    現值 {"rag_query":{"kb_ids":["b62f123f(FAQ)"]}} → 加入 559538a4(DM)（預期 1 row）
UPDATE bots SET tool_configs = jsonb_set(
  tool_configs::jsonb,
  '{rag_query,kb_ids}',
  '["b62f123f-bd69-471d-bb5d-44d5ce8c6788", "559538a4-d2ac-46e8-8e2c-1d04b599d7e6"]'::jsonb
)::json
WHERE id = '2feba9a0-47b0-49d2-94ee-494fde39d926'
  AND NOT (tool_configs::jsonb -> 'rag_query' -> 'kb_ids') @> '"559538a4-d2ac-46e8-8e2c-1d04b599d7e6"';

-- Verify：
-- SELECT description FROM bot_workers WHERE bot_id='2feba9a0-47b0-49d2-94ee-494fde39d926' AND name='商品查詢';
-- SELECT tool_configs FROM bots WHERE id='2feba9a0-47b0-49d2-94ee-494fde39d926';
