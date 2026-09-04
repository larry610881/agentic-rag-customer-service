-- Issue #68 P7c — notification_channels.notify_abuse：是否接收異常控管告警（L3/L4、fail-open、429 突增、每日摘要）
-- 既有渠道預設 TRUE（Teams 為第一通路）；冪等

ALTER TABLE notification_channels
    ADD COLUMN IF NOT EXISTS notify_abuse BOOLEAN NOT NULL DEFAULT TRUE;

-- 套用後記錄（每個環境各自執行）：
-- INSERT INTO _applied_migrations (filename, applied_at, applied_by, phase)
-- VALUES ('add_notification_channels_notify_abuse.sql', NOW(), 'claude-dev', 'dev');
