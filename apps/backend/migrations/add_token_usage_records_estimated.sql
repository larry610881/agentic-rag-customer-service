-- Issue #99 一-2 — 生成中斷線的部分計費：usage 為估算值時標記 estimated
-- Plan: docs/api-contract-review-2026-09-16.md §4（另案）
-- Issue: #99

ALTER TABLE token_usage_records
    ADD COLUMN IF NOT EXISTS estimated BOOLEAN NOT NULL DEFAULT FALSE;
