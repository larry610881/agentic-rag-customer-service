-- 康達盛通 POC 反饋修復（問題 3 / 4 / 1 短期）— prompt 連結規則 + 純文字格式 + guard 模型降級
-- Plan: .claude/plans/poc-feedback-fix-plan.md WP-B1 + WP-C
-- 目標環境：dev-vm（local-docker 無 carrefour 資料，不適用）
-- 影響範圍：LINE bot「家樂福subagent測試」(2feba9a0) 的 4 個 worker + bot_prompt + 全域 guard 設定

-- ─────────────────────────────────────────────────────────
-- 1. 問題 3：連結規則修正 — 高階客服 worker（預期 1 row）
UPDATE bot_workers SET worker_prompt = replace(worker_prompt,
  '- 禁止在回覆中硬寫電話、URL 或連結（按鈕會自動顯示）',
  '- 禁止自行編造或憑記憶輸出電話、URL、連結（轉真人按鈕由系統自動顯示）
- 知識庫（rag_query）檢索結果中出現的官方連結，應原樣保留在回覆中')
WHERE bot_id = '2feba9a0-47b0-49d2-94ee-494fde39d926' AND name = '高階客服';

-- 2. 問題 3：連結規則修正 — 商品查詢 worker（預期 1 row）
UPDATE bot_workers SET worker_prompt = replace(worker_prompt,
  '禁止在回覆中嵌入 URL 或重複列出價格（圖卡會顯示）。',
  '禁止重複列出價格（圖卡會顯示）；禁止自行編造連結，但 rag_query 檢索結果中的官方連結應原樣保留。')
WHERE bot_id = '2feba9a0-47b0-49d2-94ee-494fde39d926' AND name = '商品查詢';

-- 3. 問題 3：連結規則修正 — bot_prompt（預期 1 row）
UPDATE bots SET bot_prompt = replace(bot_prompt,
  '- **禁止在回覆中硬寫客服電話、URL、連結**（工具會自動處理）',
  '- **禁止自行編造或憑記憶輸出客服電話、URL、連結**（轉真人與圖卡由工具自動處理）
  - **知識庫檢索結果中出現的官方連結，應原樣保留輸出**')
WHERE id = '2feba9a0-47b0-49d2-94ee-494fde39d926';

-- ─────────────────────────────────────────────────────────
-- 4. 問題 4：輸出格式規範 — 4 個 worker append（冪等，預期首跑 4 rows）
UPDATE bot_workers SET worker_prompt = worker_prompt || '

# 輸出格式（純文字通路）
- 輸出純文字，禁止使用 **、#、` 等 Markdown 符號（LINE 無法渲染，會原樣顯示）
- 條列用「・」開頭，不要用「- 」或「* 」'
WHERE bot_id = '2feba9a0-47b0-49d2-94ee-494fde39d926'
  AND worker_prompt NOT LIKE '%輸出格式（純文字通路）%';

-- 5. 問題 4：輸出格式規範 — bot_prompt append（冪等，預期首跑 1 row）
UPDATE bots SET bot_prompt = bot_prompt || '

  ## 輸出格式（純文字通路）
  - 輸出純文字，禁止使用 **、#、` 等 Markdown 符號（LINE 無法渲染，會原樣顯示）
  - 條列用「・」開頭，不要用「- 」或「* 」'
WHERE id = '2feba9a0-47b0-49d2-94ee-494fde39d926'
  AND bot_prompt NOT LIKE '%輸出格式（純文字通路）%';

-- ─────────────────────────────────────────────────────────
-- 6. 問題 1 短期：input guard 模型降級 Sonnet → Haiku（預期 1 row）
--    每則訊息的前置阻塞呼叫，Sonnet 級延遲明顯高於 Haiku 級；
--    程式預設本就是 claude-haiku-4-5（prompt_guard_service.DEFAULT_GUARD_MODEL）
UPDATE guard_rules_configs
SET llm_guard_model = 'anthropic:claude-haiku-4-5'
WHERE id = 'default' AND llm_guard_model = 'anthropic:claude-sonnet-5';

-- ─────────────────────────────────────────────────────────
-- Verify（執行後貼回對話確認）：
-- SELECT name, worker_prompt LIKE '%應原樣保留%' AS link_rule,
--        worker_prompt LIKE '%輸出格式（純文字通路）%' AS fmt_rule
-- FROM bot_workers WHERE bot_id = '2feba9a0-47b0-49d2-94ee-494fde39d926';
-- SELECT bot_prompt LIKE '%應原樣保留輸出%' AS link_rule,
--        bot_prompt LIKE '%輸出格式（純文字通路）%' AS fmt_rule
-- FROM bots WHERE id = '2feba9a0-47b0-49d2-94ee-494fde39d926';
-- SELECT llm_guard_model FROM guard_rules_configs WHERE id = 'default';
