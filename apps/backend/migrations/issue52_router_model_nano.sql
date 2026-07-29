-- Issue #52 E4 — LINE POC bot 意圖分類 router 降級為 gpt-5-nano
-- 意圖分類 + 查詢改寫為簡單分類任務，router_model 空值時 fallback 至
-- bot 主模型 gpt-5.4（實測 guard∥分類段 1.77s 的主因）。
-- 資料變更（非 DDL），冪等：重跑結果相同。

UPDATE bots
SET router_model = 'openai:gpt-5-nano'
WHERE id = '2feba9a0-47b0-49d2-94ee-494fde39d926';  -- LINE 專用客服（家樂福 POC）
-- 預期影響 row 數：1
