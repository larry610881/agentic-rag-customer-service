-- Issue #67 P2 — 租戶 API key（機器憑證：client_id + client_secret）
-- secret 只存 sha256(salt+secret) 與前綴；撤銷時 token_version +1 讓已發票即刻失效
-- 冪等：IF NOT EXISTS，可重複執行

CREATE TABLE IF NOT EXISTS api_keys (
    id              VARCHAR(36)  PRIMARY KEY,
    tenant_id       VARCHAR(36)  NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    name            VARCHAR(100) NOT NULL,
    description     TEXT         NOT NULL DEFAULT '',
    secret_hash     VARCHAR(64)  NOT NULL,
    secret_salt     VARCHAR(32)  NOT NULL,
    secret_prefix   VARCHAR(16)  NOT NULL,
    scopes          JSON         NOT NULL DEFAULT '[]',
    allowed_bot_ids JSON         NOT NULL DEFAULT '[]',
    expires_at      TIMESTAMPTZ  NULL,
    revoked_at      TIMESTAMPTZ  NULL,
    token_version   INTEGER      NOT NULL DEFAULT 1,
    last_used_at    TIMESTAMPTZ  NULL,
    created_by      VARCHAR(36)  NULL,
    created_at      TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_api_keys_tenant_id ON api_keys(tenant_id);

-- 套用後記錄（每個環境各自執行）：
-- INSERT INTO _applied_migrations (filename, applied_at, applied_by, phase)
-- VALUES ('add_api_keys.sql', NOW(), 'claude-dev', 'dev');
