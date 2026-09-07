-- Issue #75 — 防護階段三層設定：guard_settings（platform / profile / tenant）+ bots.guard_stages
-- Plan: .claude/plans/billing-guard-audit-plan-2026-09-07.md §4.3
-- 只有 system_admin 可寫三層；bots.guard_stages NULL = 繼承租戶有效值（只能是有效值的超集）。冪等。

CREATE TABLE IF NOT EXISTS guard_settings (
    id          VARCHAR(36) PRIMARY KEY,
    scope_kind  VARCHAR(20) NOT NULL,
    scope_id    VARCHAR(64) NOT NULL,
    overrides   JSON        NOT NULL DEFAULT '{}',
    updated_by  VARCHAR(36) NULL,
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_guard_settings_scope UNIQUE (scope_kind, scope_id)
);

ALTER TABLE bots
    ADD COLUMN IF NOT EXISTS guard_stages JSON NULL;

-- 套用後記錄（每個環境各自執行）：
-- INSERT INTO _applied_migrations (filename, applied_at, applied_by, phase)
-- VALUES ('add_guard_settings.sql', NOW(), 'claude-dev', 'dev');
