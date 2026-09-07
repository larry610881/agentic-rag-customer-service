-- Issue #74 — tenants 加額度用盡策略 / 被擋文案覆寫（NULL = 沿用方案）
-- Plan: .claude/plans/billing-guard-audit-plan-2026-09-07.md §3.2
-- Issue: #74
-- 冪等：IF NOT EXISTS，可重複執行。

ALTER TABLE tenants
    ADD COLUMN IF NOT EXISTS exhaustion_policy_override VARCHAR(12) NULL,
    ADD COLUMN IF NOT EXISTS block_message_override     TEXT        NULL;

COMMENT ON COLUMN tenants.exhaustion_policy_override IS 'auto_topup | block | NULL（沿用方案 exhaustion_policy）';
COMMENT ON COLUMN tenants.block_message_override IS '被擋固定文案覆寫；NULL → plans.block_message → 平台預設常數';

-- 驗證：
-- SELECT column_name, data_type, is_nullable FROM information_schema.columns
-- WHERE table_name='tenants' AND column_name IN ('exhaustion_policy_override','block_message_override');

-- 套用後紀錄（依目標環境 phase 填寫）：
-- INSERT INTO _applied_migrations (filename, applied_at, applied_by, phase)
-- VALUES ('add_tenants_exhaustion_policy.sql', NOW(), 'claude-dev', 'dev');
