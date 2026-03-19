-- Add diagnostic notification fields to notification_channels
ALTER TABLE notification_channels ADD COLUMN IF NOT EXISTS notify_diagnostics BOOLEAN NOT NULL DEFAULT FALSE;
ALTER TABLE notification_channels ADD COLUMN IF NOT EXISTS diagnostic_severity VARCHAR(20) NOT NULL DEFAULT 'critical';
