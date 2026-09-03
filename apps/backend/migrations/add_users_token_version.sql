-- Issue #67 P3 — users.token_version：改密碼 / 重設密碼時 +1，票內 ver 不符即拒
-- 冪等：IF NOT EXISTS；既有使用者一律 1（既有票不受影響）

ALTER TABLE users
    ADD COLUMN IF NOT EXISTS token_version INTEGER NOT NULL DEFAULT 1;

-- 套用後記錄（每個環境各自執行）：
-- INSERT INTO _applied_migrations (filename, applied_at, applied_by, phase)
-- VALUES ('add_users_token_version.sql', NOW(), 'claude-dev', 'dev');
