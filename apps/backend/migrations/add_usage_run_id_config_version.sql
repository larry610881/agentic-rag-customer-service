-- Issue #54 Phase B — Eval token 分流：run_id / config_version_id 歸因欄位
-- Plan: docs/prompt-gate-spec.md §7.2 / §7.3
-- Issue: #54
-- 附帶：補齊 ORM 已宣告但 schema.sql drift 缺失的 3 個既有索引（§7.3 #8）。
-- 新分類 eval_gate / prompt_optimize / playground 為程式層 enum，
-- request_type VARCHAR(20) 容納無虞（最長 prompt_optimize=15），無需 DDL。

ALTER TABLE token_usage_records
    ADD COLUMN IF NOT EXISTS run_id            VARCHAR(36),
    ADD COLUMN IF NOT EXISTS config_version_id VARCHAR(36);

CREATE INDEX IF NOT EXISTS ix_token_usage_records_run_id
    ON token_usage_records (run_id);

-- schema drift 補齊（ORM __table_args__ 有、DB 缺）
CREATE INDEX IF NOT EXISTS ix_token_usage_records_tenant_created
    ON token_usage_records (tenant_id, created_at);
CREATE INDEX IF NOT EXISTS ix_token_usage_records_message_id
    ON token_usage_records (message_id);
CREATE INDEX IF NOT EXISTS ix_token_usage_records_tenant_bot_created
    ON token_usage_records (tenant_id, bot_id, created_at);
