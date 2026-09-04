-- Issue #68 P7b — widget 宿主身分綁定：每租戶一把 identity secret（加密存放、可輪替、可停用、可強制驗證）
-- 冪等

CREATE TABLE IF NOT EXISTS tenant_identity_secrets (
    tenant_id         VARCHAR(36) PRIMARY KEY REFERENCES tenants(id) ON DELETE CASCADE,
    secret_encrypted  TEXT        NOT NULL,
    is_enabled        BOOLEAN     NOT NULL DEFAULT TRUE,
    enforce_verified  BOOLEAN     NOT NULL DEFAULT FALSE,
    rotated_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at        TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 套用後記錄（每個環境各自執行）：
-- INSERT INTO _applied_migrations (filename, applied_at, applied_by, phase)
-- VALUES ('add_tenant_identity_secrets.sql', NOW(), 'claude-dev', 'dev');
