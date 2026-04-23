-- S-Token-Gov.x follow-up — token_usage_records 加 kb_id 欄位
-- 動機：admin Token 用量頁要分辨 bot 來源 vs KB 來源。原 schema 只有 bot_id，
--       KB 類任務 (OCR / Contextual Retrieval / Auto Classification / PDF Rename / Embedding)
--       現在能指向具體 KB，UI 可顯示 KB 名稱 + 連結。
-- Source plan: admin Token 用量頁 B+C 設計 Phase 2

ALTER TABLE token_usage_records
    ADD COLUMN IF NOT EXISTS kb_id VARCHAR(36) NULL;

CREATE INDEX IF NOT EXISTS ix_token_usage_records_tenant_kb_created
    ON token_usage_records (tenant_id, kb_id, created_at);
