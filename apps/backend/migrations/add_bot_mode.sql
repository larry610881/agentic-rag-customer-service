-- Issue #66 — bot 層級快速 / 深度 profile（fast | deep）
-- Plan: docs/onboarding-and-bot-wizard-requirement-brief.md §需求三（bot 層級開關）
-- Issue: #66
-- 冪等：IF NOT EXISTS，可重複執行；既有 bot 一律 deep（行為不變）

ALTER TABLE bots
    ADD COLUMN IF NOT EXISTS mode VARCHAR(10) NOT NULL DEFAULT 'deep';

-- 套用後記錄（每個環境各自執行）：
-- INSERT INTO _applied_migrations (filename, applied_at, applied_by, phase)
-- VALUES ('add_bot_mode.sql', NOW(), 'claude-dev', 'dev');
