-- Issue #92 — mode 由執行期覆蓋降級為預設填值：新增兩個可組合的行為欄位並回填
--
-- 背景：`bot.mode` 原本在管線裡硬關 rerank / 查詢改寫 / HyDE / 記憶 / 工具，
--   導致後台開關可以打開、存檔成功、實際完全不生效且無提示（UI 說謊）。
--   程式已改為只讀各自欄位，`mode` 降級為「上次套用的預設」標籤。
--
-- ⚠️ 本檔的 UPDATE 是**行為保存**：把既有 bot 依其 mode 回填成等效設定。
--   不執行回填 = 既有 kb bot 會突然開始 rerank / 升級 ReAct / 抽記憶（行為位移）。
--   欄位預設值（direct_retrieval=false、escalate_on_miss=true）等於舊 deep 行為，
--   所以 deep bot 不需回填。
--
-- Plan: Issue #92
-- 冪等：ADD COLUMN IF NOT EXISTS + 依 mode 判斷的 UPDATE，可重跑

-- ① 新增欄位（預設值 = 舊 deep 行為）
ALTER TABLE bots
    ADD COLUMN IF NOT EXISTS direct_retrieval BOOLEAN NOT NULL DEFAULT FALSE;

ALTER TABLE bots
    ADD COLUMN IF NOT EXISTS escalate_on_miss BOOLEAN NOT NULL DEFAULT TRUE;

-- ② 回填 kb：檢索一次 + 生成一次，未命中直接回話術，不 rerank / 不改寫 / 不記憶 / 無工具
UPDATE bots
SET direct_retrieval = TRUE,
    escalate_on_miss = FALSE,
    rerank_enabled = FALSE,
    query_rewrite_enabled = FALSE,
    hyde_enabled = FALSE,
    memory_enabled = FALSE
WHERE mode = 'kb';

-- ③ 回填 fast：走快速道，未命中升級 ReAct，但不 rerank / 不改寫
UPDATE bots
SET direct_retrieval = TRUE,
    escalate_on_miss = TRUE,
    rerank_enabled = FALSE,
    query_rewrite_enabled = FALSE,
    hyde_enabled = FALSE
WHERE mode = 'fast';

-- ④ deep 沿用欄位預設（direct_retrieval=false、escalate_on_miss=true），不需回填

-- ⑤ 紀錄
INSERT INTO _applied_migrations (filename, applied_at, applied_by, phase)
VALUES ('add_bot_composable_mode_fields.sql', NOW(), 'claude-dev', 'dev')
ON CONFLICT (filename) DO NOTHING;

-- ============ 驗證（執行後立即跑）============
-- SELECT mode, direct_retrieval, escalate_on_miss, rerank_enabled,
--        query_rewrite_enabled, hyde_enabled, memory_enabled, count(*)
--   FROM bots GROUP BY 1,2,3,4,5,6,7 ORDER BY 1;
--   期望：mode='kb' 全部 (t,f,f,f,f,f)；mode='fast' 全部 (t,t,f,f,f)；
--         mode='deep' 為 (f,t,...) 且其餘欄位維持原值
