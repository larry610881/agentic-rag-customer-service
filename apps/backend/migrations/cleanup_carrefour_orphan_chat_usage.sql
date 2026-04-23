-- S-ConvInsights.1 Token tab Bug fix
-- 清除 carrefour 歷史 chat-side token_usage_records（message_id=NULL 無法 JOIN messages）
-- 這 13 筆在 message_id bug fix 前產生，無法事後回填（時間戳匹配誤差 30-50%）
--
-- 保留 2 筆 KB-side（contextual_retrieval + auto_classification）— 本就不該有 message_id
--
-- 預期影響：13 rows deleted

DELETE FROM token_usage_records
WHERE tenant_id = 'cc61d4c2-51ec-4499-ae7b-db0976165c61'
  AND message_id IS NULL
  AND request_type IN (
    'chat_web',
    'chat_widget',
    'chat_line',
    'intent_classify',
    'conversation_summary'
  );
