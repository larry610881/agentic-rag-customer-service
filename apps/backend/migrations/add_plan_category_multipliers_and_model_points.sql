-- Issue #74 — 方案類別倍率表 + 模型點數表 + 平台計價設定（單列）
-- Plan: .claude/plans/billing-guard-audit-plan-2026-09-07.md §3.2
-- Issue: #74
-- 專案無既有全域單列 platform_settings 表（abuse_settings 為 scope 多列），
-- 故新開 billing_settings 單列表（id='default'）存 usd_per_point（待決 Q4 預設 0.001）。
-- 冪等：IF NOT EXISTS，可重複執行。

-- 1) plan_category_multipliers：plan_id × usage_category → multiplier（0 = 不扣點）
CREATE TABLE IF NOT EXISTS plan_category_multipliers (
    plan_id        VARCHAR(36)  NOT NULL REFERENCES plans(id) ON DELETE CASCADE,
    usage_category VARCHAR(20)  NOT NULL,
    multiplier     NUMERIC(6,3) NOT NULL,
    PRIMARY KEY (plan_id, usage_category)
);

-- 2) model_pricing：模型點數表（每千 token；NULL = 未設 → 用平台匯率由美元換算）
ALTER TABLE model_pricing
    ADD COLUMN IF NOT EXISTS points_per_1k_input  NUMERIC(10,4) NULL,
    ADD COLUMN IF NOT EXISTS points_per_1k_output NUMERIC(10,4) NULL;

-- 3) billing_settings：平台匯率單列
CREATE TABLE IF NOT EXISTS billing_settings (
    id            VARCHAR(8)    PRIMARY KEY DEFAULT 'default',
    usd_per_point NUMERIC(12,6) NOT NULL DEFAULT 0.001,
    updated_by    VARCHAR(36)   NULL,
    updated_at    TIMESTAMPTZ   NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE plan_category_multipliers IS 'Issue #74：方案 × 用量類別點數倍率；未列類別用 plans.default_category_multiplier';
COMMENT ON TABLE billing_settings IS 'Issue #74：平台計價設定（單列 id=default）；1 點 = usd_per_point USD';

-- 驗證：
-- \d plan_category_multipliers
-- \d billing_settings
-- SELECT column_name FROM information_schema.columns
-- WHERE table_name='model_pricing' AND column_name LIKE 'points_per_1k_%';

-- 套用後紀錄（依目標環境 phase 填寫）：
-- INSERT INTO _applied_migrations (filename, applied_at, applied_by, phase)
-- VALUES ('add_plan_category_multipliers_and_model_points.sql', NOW(), 'claude-dev', 'dev');
