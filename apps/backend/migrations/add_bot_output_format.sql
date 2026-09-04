-- Issue #70 — 知識庫問答模式（bot.mode = 'kb'）+ 結構化輸出（output_format）
-- Plan: docs/onboarding-and-bot-wizard-requirement-brief.md §3.3（kb 列）
-- Issue: #70
-- 冪等：IF NOT EXISTS，可重複執行；既有 bot 一律 output_format='text'（行為不變）。
-- bots.mode 欄位（VARCHAR(10)）沿用 add_bot_mode.sql，'kb' 值域由 application 層驗證。

ALTER TABLE bots
    ADD COLUMN IF NOT EXISTS output_format VARCHAR(20) NOT NULL DEFAULT 'text';

ALTER TABLE bots
    ADD COLUMN IF NOT EXISTS output_schema JSON NULL;

ALTER TABLE bots
    ADD COLUMN IF NOT EXISTS miss_reply TEXT NOT NULL DEFAULT '';

ALTER TABLE bots
    ADD COLUMN IF NOT EXISTS output_text_field VARCHAR(64) NOT NULL DEFAULT 'answer';

-- 套用後記錄（每個環境各自執行）：
-- INSERT INTO _applied_migrations (filename, applied_at, applied_by, phase)
-- VALUES ('add_bot_output_format.sql', NOW(), 'claude-dev', 'dev');
