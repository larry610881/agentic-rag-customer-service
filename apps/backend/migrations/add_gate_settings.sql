-- Issue #54 Phase C — 閘門三層開關：bots 六欄 + tenants flag
-- Plan: .claude/plans/prompt-gate-phase-c-plan.md §2 M1
-- Issue: #54

ALTER TABLE bots
    ADD COLUMN IF NOT EXISTS gate_mode           VARCHAR(10)      NOT NULL DEFAULT 'off',
    ADD COLUMN IF NOT EXISTS gate_soft_threshold DOUBLE PRECISION NOT NULL DEFAULT 0.8,
    ADD COLUMN IF NOT EXISTS gate_repeats        INTEGER          NOT NULL DEFAULT 3,
    ADD COLUMN IF NOT EXISTS gate_auto_publish   BOOLEAN          NOT NULL DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS gate_daily_limit    INTEGER          NOT NULL DEFAULT 20,
    ADD COLUMN IF NOT EXISTS gate_budget_usd     DOUBLE PRECISION NOT NULL DEFAULT 1.0;

ALTER TABLE tenants
    ADD COLUMN IF NOT EXISTS prompt_gate_enabled BOOLEAN NOT NULL DEFAULT FALSE;

-- system tenant 預設開啟（spec §2.1 定案 5）
UPDATE tenants SET prompt_gate_enabled = TRUE
WHERE id = '00000000-0000-0000-0000-000000000000';
