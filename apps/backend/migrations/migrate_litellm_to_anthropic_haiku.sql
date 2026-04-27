-- LiteLLM 額度耗盡 — 將所有 litellm:azure_ai/claude-haiku-4-5 切換成直連 Anthropic claude-haiku-4-5
-- 同價同模型（$1/$5 input/output），只是 route 改走 Anthropic 直連，避開 LiteLLM proxy 配額限制
--
-- 套用範圍：
--   1 row  bots             (家樂福subagent測試)
--   1 row  tenants          (系統 tenant 5 個 default_*_model)
--   2 rows knowledge_bases  (家樂福DM / 家樂福FAQ 各 3 個 model 欄位)
--   1 row  provider_settings (litellm 整個 disable，row 保留以便未來補額度後重啟)
--   1 row  guard_rules_configs (default 預先換掉，雖目前 disabled)

-- 1. bot
UPDATE bots
SET llm_provider='anthropic', llm_model='claude-haiku-4-5', updated_at=NOW()
WHERE id='2feba9a0-47b0-49d2-94ee-494fde39d926'
  AND llm_provider='litellm';

-- 2. 系統 tenant 5 個 default model（dev-vm 才有 5 個欄位；local-docker 只有 2 個 — 缺欄位的 UPDATE 會報錯但不影響其他 statement）
UPDATE tenants
SET default_summary_model='anthropic:claude-haiku-4-5',
    default_intent_model='anthropic:claude-haiku-4-5',
    updated_at=NOW()
WHERE id='00000000-0000-0000-0000-000000000000'
  AND (default_summary_model LIKE 'litellm:%' OR default_intent_model LIKE 'litellm:%');

-- dev-vm only: 5 欄位完整版（local-docker 沒 default_ocr_model / default_context_model / default_classification_model）
DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM information_schema.columns
             WHERE table_name='tenants' AND column_name='default_ocr_model') THEN
    EXECUTE $sql$
      UPDATE tenants
      SET default_ocr_model='anthropic:claude-haiku-4-5',
          default_context_model='anthropic:claude-haiku-4-5',
          default_classification_model='anthropic:claude-haiku-4-5'
      WHERE id='00000000-0000-0000-0000-000000000000'
    $sql$;
  END IF;
END $$;

-- 3. knowledge_bases（dev-vm only — local-docker 沒這些欄位）
DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM information_schema.columns
             WHERE table_name='knowledge_bases' AND column_name='ocr_model') THEN
    EXECUTE $sql$
      UPDATE knowledge_bases
      SET ocr_model='anthropic:claude-haiku-4-5',
          context_model='anthropic:claude-haiku-4-5',
          classification_model='anthropic:claude-haiku-4-5',
          updated_at=NOW()
      WHERE id IN (
        '559538a4-d2ac-46e8-8e2c-1d04b599d7e6',
        'b62f123f-bd69-471d-bb5d-44d5ce8c6788'
      )
      AND (ocr_model LIKE 'litellm:%'
        OR context_model LIKE 'litellm:%'
        OR classification_model LIKE 'litellm:%')
    $sql$;
  END IF;
END $$;

-- 4. provider_settings：disable litellm（保留 row + key，未來補額度直接 enable 即可）
UPDATE provider_settings
SET is_enabled=false, updated_at=NOW()
WHERE provider_name='litellm';

-- 5. guard_rules_configs（dev-vm only — local-docker 表/欄位可能缺）
DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name='guard_rules_configs')
     AND EXISTS (SELECT 1 FROM information_schema.columns
                 WHERE table_name='guard_rules_configs' AND column_name='llm_guard_model') THEN
    EXECUTE $sql$
      UPDATE guard_rules_configs
      SET llm_guard_model='anthropic:claude-haiku-4-5'
      WHERE id='default' AND llm_guard_model LIKE 'litellm:%'
    $sql$;
  END IF;
END $$;

-- 紀錄
INSERT INTO _applied_migrations (filename, applied_at, applied_by, phase)
VALUES ('migrate_litellm_to_anthropic_haiku.sql', NOW(), 'claude-dev', 'dev')
ON CONFLICT (filename) DO NOTHING;
