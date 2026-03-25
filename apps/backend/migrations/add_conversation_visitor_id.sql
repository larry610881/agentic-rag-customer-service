-- Add visitor_id to conversations for LINE/widget external user tracking
ALTER TABLE conversations ADD COLUMN IF NOT EXISTS visitor_id VARCHAR(128);
CREATE INDEX IF NOT EXISTS ix_conversations_visitor_bot ON conversations (visitor_id, bot_id);
