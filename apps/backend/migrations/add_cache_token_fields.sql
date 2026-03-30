-- Cache-aware token billing: add cache_read_tokens and cache_creation_tokens
-- to support accurate cost tracking for OpenAI/DeepSeek (automatic caching)
-- and Anthropic (prompt caching).
ALTER TABLE token_usage_records ADD COLUMN IF NOT EXISTS cache_read_tokens INTEGER NOT NULL DEFAULT 0;
ALTER TABLE token_usage_records ADD COLUMN IF NOT EXISTS cache_creation_tokens INTEGER NOT NULL DEFAULT 0;
