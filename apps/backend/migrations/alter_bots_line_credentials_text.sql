-- Issue #107 — bots 的 LINE 憑證 at-rest 加密：欄位由 VARCHAR(255) 改為 TEXT
--
-- 加密後的 access token 約 268 字元（LINE 長效 token 約 172 字元 + nonce 12 + tag 16，
-- base64 後再加 key id 前綴），VARCHAR(255) 放不下。改 TEXT 只放寬長度、不改內容：
-- 既有明文資料原樣保留，部署後以 scripts/reencrypt_secrets.py 轉為密文。
--
-- 冪等：ALTER COLUMN TYPE TEXT 對已是 TEXT 的欄位為 no-op。
-- 回滾：若要改回 VARCHAR(255)，必須先確認沒有任何值超過 255 字元（加密後必然超過），
--       因此一旦 reencrypt 跑過就不應回滾本 migration。

ALTER TABLE bots
    ALTER COLUMN line_channel_secret TYPE TEXT,
    ALTER COLUMN line_channel_access_token TYPE TEXT;
