-- Error Events table
CREATE TABLE IF NOT EXISTS error_events (
    id VARCHAR(36) PRIMARY KEY,
    fingerprint VARCHAR(16) NOT NULL,
    source VARCHAR(20) NOT NULL,
    error_type VARCHAR(200) NOT NULL,
    message TEXT NOT NULL,
    stack_trace TEXT,
    request_id VARCHAR(20),
    path VARCHAR(500),
    method VARCHAR(10),
    status_code INTEGER,
    tenant_id VARCHAR(36),
    user_agent TEXT,
    extra JSONB,
    resolved BOOLEAN NOT NULL DEFAULT FALSE,
    resolved_at TIMESTAMPTZ,
    resolved_by VARCHAR(200),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_error_events_fingerprint ON error_events (fingerprint);
CREATE INDEX IF NOT EXISTS ix_error_events_source ON error_events (source);
CREATE INDEX IF NOT EXISTS ix_error_events_resolved ON error_events (resolved);
CREATE INDEX IF NOT EXISTS ix_error_events_created_at ON error_events (created_at);
CREATE INDEX IF NOT EXISTS ix_error_events_tenant_id ON error_events (tenant_id);

-- Notification Channels table
CREATE TABLE IF NOT EXISTS notification_channels (
    id VARCHAR(36) PRIMARY KEY,
    channel_type VARCHAR(20) NOT NULL,
    name VARCHAR(100) NOT NULL,
    enabled BOOLEAN NOT NULL DEFAULT FALSE,
    config_encrypted TEXT NOT NULL DEFAULT '{}',
    throttle_minutes INTEGER NOT NULL DEFAULT 15,
    min_severity VARCHAR(20) NOT NULL DEFAULT 'all',
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Error Notification Logs (for throttle tracking)
CREATE TABLE IF NOT EXISTS error_notification_logs (
    id VARCHAR(36) PRIMARY KEY,
    fingerprint VARCHAR(16) NOT NULL,
    channel_id VARCHAR(36) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_error_notification_logs_fp_ch ON error_notification_logs (fingerprint, channel_id);
