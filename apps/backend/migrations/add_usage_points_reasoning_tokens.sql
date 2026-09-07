-- Issue #74 — token_usage_records 加 points / reasoning_tokens；token_ledger_topups 加 amount_points
-- Plan: .claude/plans/billing-guard-audit-plan-2026-09-07.md §3.2
-- Issue: #74（reasoning_tokens 承接 #72 的 TokenUsage.reasoning_tokens）
-- points 於記帳當下依租戶方案換算（token 制方案為 0）；歷史列一律 0，不回填（切換方案不重算歷史）。
-- 冪等：IF NOT EXISTS，可重複執行。

ALTER TABLE token_usage_records
    ADD COLUMN IF NOT EXISTS points           INTEGER NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS reasoning_tokens INTEGER NOT NULL DEFAULT 0;

ALTER TABLE token_ledger_topups
    ADD COLUMN IF NOT EXISTS amount_points INTEGER NOT NULL DEFAULT 0;

COMMENT ON COLUMN token_usage_records.points IS 'Issue #74：記帳當下依方案換算的點數（無條件進位）；token 制為 0';
COMMENT ON COLUMN token_usage_records.reasoning_tokens IS 'Issue #72/#74：推理 token（output 子集標注，不進 total）';
COMMENT ON COLUMN token_ledger_topups.amount_points IS 'Issue #74：點數制加購點數；token 制為 0';

-- 驗證：
-- SELECT table_name, column_name, column_default FROM information_schema.columns
-- WHERE (table_name='token_usage_records' AND column_name IN ('points','reasoning_tokens'))
--    OR (table_name='token_ledger_topups' AND column_name='amount_points');

-- 套用後紀錄（依目標環境 phase 填寫）：
-- INSERT INTO _applied_migrations (filename, applied_at, applied_by, phase)
-- VALUES ('add_usage_points_reasoning_tokens.sql', NOW(), 'claude-dev', 'dev');
