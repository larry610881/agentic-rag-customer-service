-- S-KB-Followup.2 — Tenant/Bot default summary/intent model
-- 擴充既有 tenant.default_xxx_model / bot.xxx_model pattern：
-- - tenant.default_summary_model: conversation summary 用的 model（若 bot.summary_model 空則用此）
-- - tenant.default_intent_model: intent classifier 用的 model（若 bot.router_model 空則用此）
-- - bot.summary_model: bot 級 summary 覆寫（router_model 已有，對應 intent classifier）

ALTER TABLE tenants
    ADD COLUMN IF NOT EXISTS default_summary_model VARCHAR(100) NOT NULL DEFAULT '',
    ADD COLUMN IF NOT EXISTS default_intent_model VARCHAR(100) NOT NULL DEFAULT '';

ALTER TABLE bots
    ADD COLUMN IF NOT EXISTS summary_model VARCHAR(100) NOT NULL DEFAULT '';
