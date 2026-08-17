-- 防護機制減法（2026-08-17）— 合併重複 prompt 區塊 + regex 規則瘦身
-- 配套程式：LINE 通路規範改由 LINE_CHANNEL_PROMPT_SUFFIX 注入一次；
--   LLM input/output guard 程式碼已移除（DB 欄位保留、不再生效）；
--   角色扮演類 regex 交給意圖分類器語意判定。
-- 目標 bot：2feba9a0-47b0-49d2-94ee-494fde39d926
-- 冪等：regexp_replace / split_part 對已清理的字串為 no-op

-- ① worker prompt：移除「# 輸出格式（純文字通路）」起的尾段（含今早追加的「# 回覆長度」）
UPDATE bot_workers
SET worker_prompt = rtrim(split_part(worker_prompt, E'\n\n# 輸出格式（純文字通路）', 1))
WHERE bot_id = '2feba9a0-47b0-49d2-94ee-494fde39d926'
  AND worker_prompt LIKE '%# 輸出格式（純文字通路）%';

-- ② bot_prompt：移除尾段「## 輸出格式（純文字通路）」區塊
UPDATE bots
SET bot_prompt = rtrim(regexp_replace(bot_prompt, E'\\n\\s*## 輸出格式（純文字通路）[\\s\\S]*$', ''))
WHERE id = '2feba9a0-47b0-49d2-94ee-494fde39d926'
  AND bot_prompt LIKE '%## 輸出格式（純文字通路）%';

-- ②b bot_prompt：與 LINE 後綴「≤150 字」衝突的「不限字數」字樣改掉
UPDATE bots
SET bot_prompt = replace(bot_prompt, '條列式呈現，不限字數但避免冗餘', '條列式呈現，簡潔不冗餘')
WHERE id = '2feba9a0-47b0-49d2-94ee-494fde39d926';

-- ③ input_rules 25 → 17：移除角色扮演類 8 條（你是/扮演/假裝/pretend/act as/DAN mode/邪惡模式/越獄模式）
--    → 語意判定交給意圖分類器；保留 DB 既有較完整的洩漏/覆蓋/結構標記規則
UPDATE guard_rules_configs
SET input_rules = '[{"type": "regex", "enabled": true, "pattern": "(忽略|忽視|跳過|略過|取消|廢除)(以上|上述|上面|前面|前述|之前|先前|剛才|方才)?(所有|全部)?(的)?(指令|提示|規則|設定|prompt)"}, {"type": "regex", "enabled": true, "pattern": "ignore\\s+(all\\s+|the\\s+)?(previous\\s+|above\\s+|prior\\s+|earlier\\s+)?(instructions|prompts|rules|directives)"}, {"type": "regex", "enabled": true, "pattern": "disregard\\s+(all\\s+|the\\s+|previous\\s+|above\\s+)?(instructions|prompt|rules)"}, {"type": "regex", "enabled": true, "pattern": "(forget|override|bypass)\\s+(all\\s+|the\\s+|your\\s+|previous\\s+|above\\s+)?(instructions|prompt|rules|system)"}, {"type": "regex", "enabled": true, "pattern": "\\b(?-i:DAN)\\b"}, {"type": "keyword", "enabled": true, "pattern": "developer mode"}, {"type": "keyword", "enabled": true, "pattern": "jailbreak"}, {"type": "regex", "enabled": true, "pattern": "(system|系統|內部|底層)\\s*(prompt|提示詞|提示|指令|規則|設定|configuration)"}, {"type": "regex", "enabled": true, "pattern": "(複述|重複|顯示|輸出|印出|列出|揭露|告訴我)\\s*(你的|系統)?\\s*(指令|提示詞|prompt|規則|設定)"}, {"type": "regex", "enabled": true, "pattern": "(reveal|show|output|print|repeat|leak|expose|tell\\s+me)\\s+(your\\s+)?(system\\s+|original\\s+|initial\\s+)?(prompt|instructions|rules|configuration)"}, {"type": "regex", "enabled": true, "pattern": "\\[SYSTEM\\]"}, {"type": "regex", "enabled": true, "pattern": "<\\|im_start\\|>\\s*system"}, {"type": "regex", "enabled": true, "pattern": "<system>|</system>"}, {"type": "regex", "enabled": true, "pattern": "---\\s*(END|NEW|RESET)\\s+(OF\\s+)?(CONVERSATION|SYSTEM\\s+)?PROMPT"}, {"type": "regex", "enabled": true, "pattern": "(列出|顯示|輸出|揭露)(你的|所有|全部)?(工具|tool|function)\\s*(定義|清單|列表|definition|schema)"}, {"type": "regex", "enabled": true, "pattern": "(api[_\\s\\-]*key|api金鑰|金鑰|secret\\s*key|access\\s*token)"}, {"type": "regex", "enabled": true, "pattern": "(連接|連線|使用|呼叫)(的|哪些|什麼)?(資料庫|database|db|qdrant|milvus|postgres)"}]'::json
WHERE id = 'default';

INSERT INTO _applied_migrations (filename, applied_at, applied_by, phase)
VALUES ('guard_slimming_2026-08-17.sql', NOW(), 'claude-dev', 'dev')
ON CONFLICT (filename) DO NOTHING;
