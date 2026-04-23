-- 一次性回填：carrefour 歷史 contextual_retrieval / auto_classification token_usage 記錄
-- 綁到家樂福FAQ KB (b62f123f-bd69-471d-bb5d-44d5ce8c6788)
--
-- 背景：add_kb_id_to_token_usage.sql 前已產生的 2 筆 row 無 kb_id。
-- User 確認這 2 筆應歸屬家樂福FAQ。
--
-- 預期影響：2 rows
-- 必須在 add_kb_id_to_token_usage.sql 之後執行

UPDATE token_usage_records
SET kb_id = 'b62f123f-bd69-471d-bb5d-44d5ce8c6788'
WHERE tenant_id = 'cc61d4c2-51ec-4499-ae7b-db0976165c61'
  AND kb_id IS NULL
  AND request_type IN ('contextual_retrieval', 'auto_classification');
