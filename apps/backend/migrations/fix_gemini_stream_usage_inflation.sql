-- Issue #90 — 修正 Gemini 相容端點串流記帳膨脹的歷史資料（DML，需 Larry 預覽核准）
--
-- 根因：Gemini 相容端點每個 chunk 都帶「累計」usage，langchain 逐 chunk 相加後寫進
-- token_usage_records。程式已修（LastUsageChatOpenAI），本檔只處理修正前的舊列。
--
-- 估算模型（無法還原真值，只能推估；推導見 Issue #90）：
--   若 N 個 chunk 各帶累計 usage，則 rec_in ≈ N × true_in，
--   rec_out ≈ true_out × (N+1)/2。以回答字元數 × 0.85 估 true_out（terra 實測平穩比值），
--   反推 N = 2 × rec_out / true_out − 1，再得 true_in = rec_in / N。
--
-- 影響範圍（2026-09-08 dry-run）：1,274 列、5 個 bot（評測 763、card-3.8 332、JSON 111、
-- 工具 67、fab-3.8 1）。input 6.60M → 1.98M，output 756k → 220k，
-- estimated_cost 7.784 → 約 2.309（牌價 $0.75 / $3.75）。
--
-- 冪等：只改 cost_recalc_at IS NULL 的列；每列在 pricing_recalc_audit 留原值。

BEGIN;

CREATE TEMP TABLE _gemini_fix AS
SELECT u.id,
       u.input_tokens  AS old_in,
       u.output_tokens AS old_out,
       u.estimated_cost AS old_cost,
       greatest(1, round(length(m.content) * 0.85))::int AS new_out,
       greatest(1, round(
           2.0 * u.output_tokens / greatest(1, round(length(m.content) * 0.85)) - 1
       ))::int AS n_chunks
FROM token_usage_records u
JOIN messages m ON m.id = u.message_id
WHERE u.request_type = 'chat_web'
  AND u.model = 'gemini-3.8-flash'
  AND u.cost_recalc_at IS NULL;

-- 預覽（執行前先看這行的輸出）
SELECT count(*) AS rows, sum(old_in) AS old_in, sum(round(old_in / n_chunks)) AS new_in,
       sum(old_out) AS old_out, sum(new_out) AS new_out,
       round(sum(old_cost)::numeric, 3) AS old_cost
FROM _gemini_fix;

-- 不寫 pricing_recalc_audit：它的 pricing_id NOT NULL 且指向 model_pricing，而
-- gemini-3.8-flash 在 model_pricing 沒有列（牌價目前來自 model_registry.py）。
-- 稽核紀錄 = 本檔的預覽輸出 + Issue #90 的 dry-run 數字；逐筆以 cost_recalc_at 標記。

UPDATE token_usage_records u
SET input_tokens   = round(f.old_in / f.n_chunks),
    output_tokens  = f.new_out,
    estimated_cost = ((f.old_in / f.n_chunks) * 0.75 + f.new_out * 3.75) / 1e6,
    cost_recalc_at = NOW()
FROM _gemini_fix f
WHERE u.id = f.id;

-- 驗證
SELECT count(*) AS fixed_rows, sum(input_tokens) AS in_after, sum(output_tokens) AS out_after,
       round(sum(estimated_cost)::numeric, 3) AS cost_after
FROM token_usage_records
WHERE request_type = 'chat_web' AND model = 'gemini-3.8-flash' AND cost_recalc_at IS NOT NULL;

-- 紀錄 migration（套用時一併執行）
-- INSERT INTO _applied_migrations (filename, applied_at, applied_by, phase)
-- VALUES ('fix_gemini_stream_usage_inflation.sql', NOW(), 'claude-dev', 'dev');

-- 確認無誤再 COMMIT；否則 ROLLBACK
-- COMMIT;
