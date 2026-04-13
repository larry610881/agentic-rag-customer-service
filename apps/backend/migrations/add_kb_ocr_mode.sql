-- Add ocr_mode column to knowledge_bases table
ALTER TABLE knowledge_bases
    ADD COLUMN IF NOT EXISTS ocr_mode VARCHAR(20) NOT NULL DEFAULT 'general';
