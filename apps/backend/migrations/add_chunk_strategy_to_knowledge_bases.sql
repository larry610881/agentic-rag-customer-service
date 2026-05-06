-- Issue #45 — Per-KB chunk_strategy override (1+A separator splitter)
-- Plan: .claude/plans/1-a-prancy-codd.md
--
-- 預設空字串 → 走全域 config.chunk_strategy（不變既有行為）
-- 設 'separator' → 路由到 SeparatorTextSplitterService（DM catalog 用）
-- 其他白名單值：'auto' | 'recursive' | 'json_record' | 'csv_row'
-- 實際值的白名單由後端 API validator 強制（避免 DB 端硬綁 enum 影響未來擴充）

ALTER TABLE knowledge_bases
    ADD COLUMN IF NOT EXISTS chunk_strategy VARCHAR(20)
        NOT NULL DEFAULT '';

-- Verify
SELECT column_name, data_type, column_default, is_nullable
FROM information_schema.columns
WHERE table_name='knowledge_bases' AND column_name='chunk_strategy';

-- Record (run separately on each environment)
-- INSERT INTO _applied_migrations (filename, applied_at, applied_by, phase)
-- VALUES ('add_chunk_strategy_to_knowledge_bases.sql', NOW(), 'claude-dev', 'dev');
