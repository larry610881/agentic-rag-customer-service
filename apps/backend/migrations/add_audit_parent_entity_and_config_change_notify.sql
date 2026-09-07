-- Issue #77 — worker 稽核連結所屬 bot + 設定變更通知
-- Plan: .claude/plans/billing-guard-audit-plan-2026-09-07.md §5
-- 1) audit_logs.parent_entity_type / parent_entity_id：worker 稽核列帶 parent=("bot", bot_id)，
--    租戶端 GET /bots/{id}/audit-logs 以 entity=bot ∪ parent=bot 一次 keyset 查詢併入。
-- 2) notification_channels.notify_config_change：渠道是否接收「設定變更」通知（預設關）。
-- 3) tenants.config_change_notify_fields：租戶勾選哪些欄位群組（model / prompt / knowledge /
--    tools / guard）變更要通知；NULL = 平台預設（model + prompt）。
-- 冪等：IF NOT EXISTS，可重複執行。

ALTER TABLE audit_logs
    ADD COLUMN IF NOT EXISTS parent_entity_type VARCHAR(40)  NULL,
    ADD COLUMN IF NOT EXISTS parent_entity_id   VARCHAR(100) NULL;

CREATE INDEX IF NOT EXISTS ix_audit_logs_parent
    ON audit_logs (parent_entity_type, parent_entity_id, created_at);

ALTER TABLE notification_channels
    ADD COLUMN IF NOT EXISTS notify_config_change BOOLEAN NOT NULL DEFAULT FALSE;

ALTER TABLE tenants
    ADD COLUMN IF NOT EXISTS config_change_notify_fields JSON NULL;

COMMENT ON COLUMN audit_logs.parent_entity_type IS 'Issue #77：所屬上層實體類型（worker → bot）';
COMMENT ON COLUMN audit_logs.parent_entity_id IS 'Issue #77：所屬上層實體 id（worker → bot_id）';
COMMENT ON COLUMN notification_channels.notify_config_change IS 'Issue #77：是否接收設定變更通知';
COMMENT ON COLUMN tenants.config_change_notify_fields IS 'Issue #77：要通知的欄位群組清單；NULL = 平台預設（model, prompt）';

-- 驗證：
-- SELECT column_name, data_type, is_nullable FROM information_schema.columns
-- WHERE (table_name='audit_logs' AND column_name IN ('parent_entity_type','parent_entity_id'))
--    OR (table_name='notification_channels' AND column_name='notify_config_change')
--    OR (table_name='tenants' AND column_name='config_change_notify_fields');
-- SELECT indexname FROM pg_indexes WHERE tablename='audit_logs' AND indexname='ix_audit_logs_parent';

-- 套用後紀錄（依目標環境 phase 填寫，每個環境各自執行）：
-- INSERT INTO _applied_migrations (filename, applied_at, applied_by, phase)
-- VALUES ('add_audit_parent_entity_and_config_change_notify.sql', NOW(), 'claude-dev', 'dev');
