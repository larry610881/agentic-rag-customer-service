-- Issue #60 — 執行時設定指紋（config_snapshots）+ 管理端變更稽核（audit_logs）
-- Plan: 紅隊追溯需求（2026-09-02 盤點）：任一 trace 可 join 出當時生效設定；
--       guard / 平台 prompt / bot / worker / tenant 旗標變更留下 actor 與 before/after
-- Issue: #60
-- 冪等：全部 IF NOT EXISTS，可重複執行

CREATE TABLE IF NOT EXISTS config_snapshots (
    hash            VARCHAR(64)  PRIMARY KEY,
    snapshot        JSON         NOT NULL,
    snapshot_schema INTEGER      NOT NULL DEFAULT 1,
    first_seen_at   TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

ALTER TABLE agent_execution_traces
    ADD COLUMN IF NOT EXISTS config_hash VARCHAR(64);
CREATE INDEX IF NOT EXISTS ix_agent_execution_traces_bot_config_hash
    ON agent_execution_traces (bot_id, config_hash);

ALTER TABLE token_usage_records
    ADD COLUMN IF NOT EXISTS config_hash VARCHAR(64);

CREATE TABLE IF NOT EXISTS audit_logs (
    id             VARCHAR(36)  PRIMARY KEY,
    tenant_id      VARCHAR(36),
    actor_user_id  VARCHAR(36),
    entity_type    VARCHAR(40)  NOT NULL,
    entity_id      VARCHAR(100) NOT NULL,
    action         VARCHAR(20)  NOT NULL,
    changed_fields JSON,
    source         VARCHAR(20)  NOT NULL DEFAULT 'api',
    created_at     TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS ix_audit_logs_entity
    ON audit_logs (entity_type, entity_id, created_at);
CREATE INDEX IF NOT EXISTS ix_audit_logs_tenant_created
    ON audit_logs (tenant_id, created_at);

-- 套用後記錄（每個環境各自執行）：
-- INSERT INTO _applied_migrations (filename, applied_at, applied_by, phase)
-- VALUES ('add_config_snapshots_and_audit_logs.sql', NOW(), 'claude-dev', 'dev');
