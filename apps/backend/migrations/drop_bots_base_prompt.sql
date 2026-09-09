-- Issue #91 — 移除 bots.base_prompt，並把優化器目標預設改為 bot_prompt
--
-- 背景：`base_prompt` 的舊語意是「取代平台 system prompt」
--   （程式碼 `bot.base_prompt or sys_cfg.system_prompt`），
--   等於租戶在後台填一個字就能關掉平台防護層。Issue #91 已在程式層移除該欄位，
--   平台防護改由 domain 常數 SECURITY_CLAUSE 無條件注入。
--
-- 影響評估（2026-09-09 於 company-poc-vm 實測）：
--   bots 中 base_prompt 非空者          0 筆
--   audit_logs 的 changed_fields 提及者  0 筆（總 81 筆）
--   bot_config_versions 快照含該鍵       2 筆，值為空字串（overlay 會略過未知鍵，不影響回朔）
--   eval_datasets                        0 筆
--
-- Plan: .claude/plans/prompt-leak-defense-plan-2026-09-08.md
-- Issue: #91（Refs #89）
--
-- ⚠️ DROP COLUMN：依 .claude/rules/migration-workflow.md 需 Larry 口頭明確確認後才可執行，
--    且 local-docker 與 company-poc-vm 各自獨立走五步流程。

-- ① 移除欄位（不可逆——執行前請確認上方影響評估仍成立）
ALTER TABLE bots
    DROP COLUMN IF EXISTS base_prompt;

-- ② 優化器目標欄位預設值改為 bot_prompt（base_prompt 已不存在）
ALTER TABLE eval_datasets
    ALTER COLUMN target_prompt SET DEFAULT 'bot_prompt';

-- ③ 既有指向已移除欄位的評測集一併轉向（POC 現為 0 筆，冪等）
UPDATE eval_datasets
SET target_prompt = 'bot_prompt'
WHERE target_prompt = 'base_prompt';

-- ④ 紀錄
INSERT INTO _applied_migrations (filename, applied_at, applied_by, phase)
VALUES ('drop_bots_base_prompt.sql', NOW(), 'claude-dev', 'dev')
ON CONFLICT (filename) DO NOTHING;

-- ============ 驗證（執行後立即跑）============
-- SELECT column_name FROM information_schema.columns
--  WHERE table_name = 'bots' AND column_name = 'base_prompt';   -- 應為 0 列
-- SELECT column_default FROM information_schema.columns
--  WHERE table_name = 'eval_datasets' AND column_name = 'target_prompt';  -- 應為 'bot_prompt'
