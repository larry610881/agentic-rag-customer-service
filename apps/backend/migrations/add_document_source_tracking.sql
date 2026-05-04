-- Issue #44 Phase 2 — External Producer Integration
-- Add source / source_id columns to documents so the bulk ingest endpoint
-- can persist the upstream producer reference (e.g. audit_log / 12345),
-- and process_document_use_case can propagate them into Milvus chunk
-- payloads (where DELETE /by-source filter expressions match against them).
--
-- Both columns are NOT NULL with empty-string default so existing rows
-- backfill cleanly without breaking the pipeline.

ALTER TABLE documents
    ADD COLUMN IF NOT EXISTS source VARCHAR(64) NOT NULL DEFAULT '';

ALTER TABLE documents
    ADD COLUMN IF NOT EXISTS source_id VARCHAR(128) NOT NULL DEFAULT '';

-- INVERTED-equivalent btree index for the (kb_id, source, source_id)
-- triplet — used when bulk ingest dedups by deleting prior documents
-- belonging to the same external source record before re-uploading.
CREATE INDEX IF NOT EXISTS ix_documents_kb_source
    ON documents (kb_id, source, source_id);
