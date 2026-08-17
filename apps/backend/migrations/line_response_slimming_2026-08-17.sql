-- LINE 回應瘦身（目標：LINE 通路回應 ≤5s）— 2026-08-17
-- 依據：dev-vm traces 07-29~07-31 avg 6.9s、≤5s 僅 8%；
--   輸出 125-279 tok（gpt-5.4 ~51 tok/s → 生成段 2.5-5s）、
--   高階客服 ReAct 2 次 LLM 4.2-5.1s、LLM input guard(haiku) 2.1s > 意圖分類 1.46s
-- 三個槓桿：① 砍輸出重量（max_tokens + prompt 長度規範）② 高階客服走快速道 ③ 關 LLM input guard
-- 目標 bot：2feba9a0-47b0-49d2-94ee-494fde39d926（LINE 專用客服（家樂福 POC））
-- 冪等：prompt 追加用 NOT LIKE 守衛；其餘 UPDATE 可重跑

-- ① max_tokens：2048/1024/512 → 450/400/300/150
UPDATE bot_workers SET max_tokens = 450 WHERE bot_id = '2feba9a0-47b0-49d2-94ee-494fde39d926' AND name = '高階客服';
UPDATE bot_workers SET max_tokens = 400 WHERE bot_id = '2feba9a0-47b0-49d2-94ee-494fde39d926' AND name = '門市服務查詢';
UPDATE bot_workers SET max_tokens = 300 WHERE bot_id = '2feba9a0-47b0-49d2-94ee-494fde39d926' AND name = '商品查詢';
UPDATE bot_workers SET max_tokens = 150 WHERE bot_id = '2feba9a0-47b0-49d2-94ee-494fde39d926' AND name = '閒聊';

-- ① worker prompt 追加「回覆長度」規範
UPDATE bot_workers
SET worker_prompt = worker_prompt || E'\n\n# 回覆長度（LINE 通路，速度優先）\n- 直接回答重點，全文不超過 120 字；條列最多 3 點\n- 不重述使用者的問題、不加開場白與結尾客套話（例：「感謝您的詢問」「如有其他問題…」）\n- 只保留回答問題所需的資訊，不補充未被詢問的延伸內容'
WHERE bot_id = '2feba9a0-47b0-49d2-94ee-494fde39d926'
  AND name IN ('高階客服', '商品查詢', '閒聊')
  AND worker_prompt NOT LIKE '%# 回覆長度%';

-- 門市服務查詢：分店清單完整性是 PM 需求，例外保留
UPDATE bot_workers
SET worker_prompt = worker_prompt || E'\n\n# 回覆長度（LINE 通路，速度優先）\n- 直接回答重點；除 FAQ 內含的分店清單需完整保留外，其餘說明不超過 80 字\n- 不重述使用者的問題、不加開場白與結尾客套話\n- 只保留回答問題所需的資訊，不補充未被詢問的延伸內容'
WHERE bot_id = '2feba9a0-47b0-49d2-94ee-494fde39d926'
  AND name = '門市服務查詢'
  AND worker_prompt NOT LIKE '%# 回覆長度%';

-- ② 高階客服走快速道（分流即檢索 → 單次生成；低分/異常自動升級 ReAct；transfer_to_human_agent 保留）
UPDATE bot_workers SET direct_retrieval = true WHERE bot_id = '2feba9a0-47b0-49d2-94ee-494fde39d926' AND name = '高階客服';

-- ③ 關閉 LLM input guard（haiku 2.1s），保留 25 條規則式 input guard；output LLM guard 原本即關閉
UPDATE guard_rules_configs SET llm_input_guard_enabled = false WHERE id = 'default';

INSERT INTO _applied_migrations (filename, applied_at, applied_by, phase)
VALUES ('line_response_slimming_2026-08-17.sql', NOW(), 'claude-dev', 'dev')
ON CONFLICT (filename) DO NOTHING;

-- ============ 回滾（品質退步時逐句執行）============
-- UPDATE bot_workers SET max_tokens = 2048 WHERE bot_id='2feba9a0-47b0-49d2-94ee-494fde39d926' AND name='高階客服';
-- UPDATE bot_workers SET max_tokens = 1024 WHERE bot_id='2feba9a0-47b0-49d2-94ee-494fde39d926' AND name IN ('門市服務查詢','商品查詢');
-- UPDATE bot_workers SET max_tokens = 512  WHERE bot_id='2feba9a0-47b0-49d2-94ee-494fde39d926' AND name='閒聊';
-- UPDATE bot_workers SET worker_prompt = split_part(worker_prompt, E'\n\n# 回覆長度', 1) WHERE bot_id='2feba9a0-47b0-49d2-94ee-494fde39d926';
-- UPDATE bot_workers SET direct_retrieval = false WHERE bot_id='2feba9a0-47b0-49d2-94ee-494fde39d926' AND name='高階客服';
-- UPDATE guard_rules_configs SET llm_input_guard_enabled = true WHERE id='default';
-- 已套用：dev-vm 2026-08-17 06:50 UTC（UPDATE 1/1/1/1/3/1/1/1，verify ✓）
