-- Intent routing: per-bot configurable intent categories with custom prompts
ALTER TABLE bots ADD COLUMN IF NOT EXISTS intent_routes JSONB NOT NULL DEFAULT '[]';
