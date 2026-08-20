-- Issue #54 — 平台通用集 bot 級勾選排除（定案更新 08-20）
-- Plan: docs/prompt-gate-spec.md §5.1
-- Issue: #54
-- 治理欄位（不進 config snapshot 白名單）；審計靠 gate run details
-- 的 excluded_platform_cases 紀錄。

ALTER TABLE bots
    ADD COLUMN IF NOT EXISTS gate_excluded_cases JSONB NOT NULL DEFAULT '[]'::jsonb;
