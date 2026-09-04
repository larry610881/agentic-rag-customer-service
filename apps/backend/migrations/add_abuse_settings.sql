-- Issue #68 P7c — 異常控管設定三層：platform（系統預設）/ profile（方案）/ tenant（租戶指定方案 + 微調）
-- 只有 system_admin 可寫；覆寫以 JSON 存，只放有改的鍵。冪等。

CREATE TABLE IF NOT EXISTS abuse_settings (
    id          VARCHAR(36) PRIMARY KEY,
    scope_kind  VARCHAR(20) NOT NULL,
    scope_id    VARCHAR(64) NOT NULL,
    overrides   JSON        NOT NULL DEFAULT '{}',
    updated_by  VARCHAR(36) NULL,
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_abuse_settings_scope UNIQUE (scope_kind, scope_id)
);

-- 套用後記錄（每個環境各自執行）：
-- INSERT INTO _applied_migrations (filename, applied_at, applied_by, phase)
-- VALUES ('add_abuse_settings.sql', NOW(), 'claude-dev', 'dev');
