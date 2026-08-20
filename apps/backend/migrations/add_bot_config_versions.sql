-- Issue #54 Phase A — Bot 設定整包版控：bot_config_versions 表
-- Plan: docs/prompt-gate-spec.md §13.2
-- Issue: #54

CREATE TABLE IF NOT EXISTS bot_config_versions (
    id              VARCHAR(36) PRIMARY KEY,
    tenant_id       VARCHAR(36) NOT NULL,
    bot_id          VARCHAR(36) NOT NULL REFERENCES bots(id) ON DELETE CASCADE,
    version_no      INTEGER     NOT NULL,
    config_snapshot JSONB       NOT NULL,
    snapshot_schema INTEGER     NOT NULL DEFAULT 1,
    changed_fields  JSONB       NOT NULL DEFAULT '[]'::jsonb,
    status          VARCHAR(20) NOT NULL DEFAULT 'draft',
        -- draft | validating | pending_publish | published | rejected
    is_current      BOOLEAN     NOT NULL DEFAULT FALSE,
    source          VARCHAR(20) NOT NULL DEFAULT 'manual',
        -- manual | optimizer | rollback | seed
    source_run_id   VARCHAR(36),
    gate_run_id     VARCHAR(36),
    gate_verdict    VARCHAR(20),
        -- pass | fail | forced | skipped
    author_user_id  TEXT,
    published_at    TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_bcv_bot_version UNIQUE (bot_id, version_no)
);

CREATE INDEX IF NOT EXISTS ix_bcv_bot_created
    ON bot_config_versions (bot_id, created_at DESC);
CREATE INDEX IF NOT EXISTS ix_bcv_tenant
    ON bot_config_versions (tenant_id);
-- is_current 唯一不變量（每 bot 至多一個線上版本）
CREATE UNIQUE INDEX IF NOT EXISTS ix_bcv_current
    ON bot_config_versions (bot_id) WHERE is_current;
