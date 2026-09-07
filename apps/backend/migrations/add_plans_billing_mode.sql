-- Issue #74 — 雙軌計價 + 額度用盡策略：plans 加 9 欄
-- Plan: .claude/plans/billing-guard-audit-plan-2026-09-07.md §3.2
-- Issue: #74
-- 既有方案預設 billing_mode='token'、exhaustion_policy='auto_topup' → 行為不變。
-- 月費沿用既有 base_price（待決 Q3 定案，不加 monthly_price）。
-- 冪等：IF NOT EXISTS，可重複執行。

ALTER TABLE plans
    ADD COLUMN IF NOT EXISTS billing_mode                VARCHAR(10)   NOT NULL DEFAULT 'token',
    ADD COLUMN IF NOT EXISTS monthly_points              INTEGER       NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS addon_pack_points           INTEGER       NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS default_category_multiplier NUMERIC(6,3)  NOT NULL DEFAULT 1,
    ADD COLUMN IF NOT EXISTS exhaustion_policy           VARCHAR(12)   NOT NULL DEFAULT 'auto_topup',
    ADD COLUMN IF NOT EXISTS tenant_may_change_policy    BOOLEAN       NOT NULL DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS auto_topup_monthly_cap      INTEGER       NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS grace_percent               NUMERIC(5,2)  NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS block_message               TEXT          NOT NULL DEFAULT '';

COMMENT ON COLUMN plans.billing_mode IS 'token（預設）| points；token 永遠是事實來源，點數是換算層';
COMMENT ON COLUMN plans.exhaustion_policy IS 'auto_topup（預設）| block；獨立於計價模式';
COMMENT ON COLUMN plans.auto_topup_monthly_cap IS '自動展延每月次數上限；0 = 不限';
COMMENT ON COLUMN plans.grace_percent IS 'block 策略的寬限百分比（以月基礎額度計）；預設 0';

-- 驗證：
-- SELECT column_name, data_type, column_default FROM information_schema.columns
-- WHERE table_name='plans' AND column_name IN ('billing_mode','monthly_points','addon_pack_points',
--   'default_category_multiplier','exhaustion_policy','tenant_may_change_policy',
--   'auto_topup_monthly_cap','grace_percent','block_message');

-- 套用後紀錄（依目標環境 phase 填寫）：
-- INSERT INTO _applied_migrations (filename, applied_at, applied_by, phase)
-- VALUES ('add_plans_billing_mode.sql', NOW(), 'claude-dev', 'dev');
