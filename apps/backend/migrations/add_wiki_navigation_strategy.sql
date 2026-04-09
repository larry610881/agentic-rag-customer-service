-- Sprint W.3 — Add wiki_navigation_strategy column to bots
-- 為 Bot 新增 wiki navigation strategy 欄位，MVP 只支援 "keyword_bfs"，
-- Post-MVP 可擴充為 cluster_picker / hybrid / embedding / substring
-- Plan: .claude/plans/luminous-launching-lobster.md
-- Issue: #26

ALTER TABLE bots
    ADD COLUMN IF NOT EXISTS wiki_navigation_strategy
        VARCHAR(30) NOT NULL DEFAULT 'keyword_bfs';
