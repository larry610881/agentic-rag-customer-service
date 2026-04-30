-- Issue #43 — Bot-level RAG retrieval modes
-- raw / rewrite / hyde 多選 + 各 mode 獨立 model + extra_hint
--
-- - rag_retrieval_modes: JSONB list of enum string ("raw" | "rewrite" | "hyde")
--   Default ["raw"]（向後相容；至少 1 個由 application layer 強制）
-- - query_rewrite_*: bot 級 LLM rewrite 設定
-- - hyde_*: bot 級 HyDE（hypothetical answer）設定

ALTER TABLE bots
    ADD COLUMN IF NOT EXISTS rag_retrieval_modes JSONB
        NOT NULL DEFAULT '["raw"]'::jsonb,
    ADD COLUMN IF NOT EXISTS query_rewrite_enabled BOOLEAN
        NOT NULL DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS query_rewrite_model VARCHAR(100)
        NOT NULL DEFAULT '',
    ADD COLUMN IF NOT EXISTS query_rewrite_extra_hint TEXT
        NOT NULL DEFAULT '',
    ADD COLUMN IF NOT EXISTS hyde_enabled BOOLEAN
        NOT NULL DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS hyde_model VARCHAR(100)
        NOT NULL DEFAULT '',
    ADD COLUMN IF NOT EXISTS hyde_extra_hint TEXT
        NOT NULL DEFAULT '';
