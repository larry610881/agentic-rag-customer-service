-- Issue #54 Phase C — 題集雙層設計旗標：case enabled + 平台通用集標記
-- Plan: .claude/plans/prompt-gate-phase-c-plan.md §2 M2
-- Issue: #54

ALTER TABLE eval_test_cases
    ADD COLUMN IF NOT EXISTS enabled BOOLEAN NOT NULL DEFAULT TRUE;

ALTER TABLE eval_datasets
    ADD COLUMN IF NOT EXISTS is_platform_base BOOLEAN NOT NULL DEFAULT FALSE;

CREATE INDEX IF NOT EXISTS ix_eval_datasets_bot_id ON eval_datasets (bot_id);
