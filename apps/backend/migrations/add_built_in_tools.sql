-- Sprint S-Gov.2: built-in tool tenant scope 管控
-- Mirror of mcp_server_registrations scope/tenant_ids pattern.

CREATE TABLE IF NOT EXISTS built_in_tools (
    name VARCHAR(64) PRIMARY KEY,
    label VARCHAR(128) NOT NULL,
    description VARCHAR(2000) NOT NULL DEFAULT '',
    requires_kb BOOLEAN NOT NULL DEFAULT FALSE,
    scope VARCHAR(20) NOT NULL DEFAULT 'global',
    tenant_ids JSON NOT NULL DEFAULT '[]',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_built_in_tools_scope ON built_in_tools(scope);
