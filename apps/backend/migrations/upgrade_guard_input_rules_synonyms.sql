-- 升級 prompt guard input rules 涵蓋更多同義詞與偽裝句型
-- 不破壞既有 rule，整批 replace 為涵蓋更廣的版本
--
-- 主要強化點：
--   ① 「以上指令」改成 (以上|上述|上面|前面|前述|之前|先前|剛才|方才) — 補同義詞
--   ② 「你現在是 X 助手」型偽裝 — 新增 (角色冒充偽客服化)
--   ③ system prompt 套取詞彙範圍擴大
--   ④ 「我是」「我叫」開頭的偽冒身份 — 新增
--   ⑤ 動詞群擴充：忽略 → 忽略 / 忽視 / 跳過 / 略過 / 取消 / 廢除

UPDATE guard_rules_configs
SET input_rules = $$[
  {"pattern": "(忽略|忽視|跳過|略過|取消|廢除)(以上|上述|上面|前面|前述|之前|先前|剛才|方才)?(所有|全部)?(的)?(指令|提示|規則|設定|prompt)", "type": "regex", "enabled": true},
  {"pattern": "ignore\\s+(all\\s+|the\\s+)?(previous\\s+|above\\s+|prior\\s+|earlier\\s+)?(instructions|prompts|rules|directives)", "type": "regex", "enabled": true},
  {"pattern": "disregard\\s+(all\\s+|the\\s+|previous\\s+|above\\s+)?(instructions|prompt|rules)", "type": "regex", "enabled": true},
  {"pattern": "(forget|override|bypass)\\s+(all\\s+|the\\s+|your\\s+|previous\\s+|above\\s+)?(instructions|prompt|rules|system)", "type": "regex", "enabled": true},

  {"pattern": "你(現在|的)?(是|當作?|扮演|變成|改為)\\S{0,12}(助手|助理|秘書|專員|顧問|工程師|老師|專家|機器人|AI|gpt|claude)", "type": "regex", "enabled": true},
  {"pattern": "你(現在|的)?(是|角色|身份)(是|變成|改為|扮演)", "type": "regex", "enabled": true},
  {"pattern": "(假裝|假設|想像)(你|妳)(是|為)", "type": "regex", "enabled": true},

  {"pattern": "DAN mode", "type": "keyword", "enabled": true},
  {"pattern": "\\b(?-i:DAN)\\b", "type": "regex", "enabled": true},
  {"pattern": "developer mode", "type": "keyword", "enabled": true},
  {"pattern": "jailbreak", "type": "keyword", "enabled": true},
  {"pattern": "邪惡模式", "type": "keyword", "enabled": true},
  {"pattern": "越獄模式", "type": "keyword", "enabled": true},
  {"pattern": "pretend\\s+(you\\s+are|to\\s+be)", "type": "regex", "enabled": true},
  {"pattern": "act\\s+as\\s+(if\\s+you\\s+(are|were)|a)", "type": "regex", "enabled": true},

  {"pattern": "(system|系統|內部|底層)\\s*(prompt|提示詞|提示|指令|規則|設定|configuration)", "type": "regex", "enabled": true},
  {"pattern": "(複述|重複|顯示|輸出|印出|列出|揭露|告訴我)\\s*(你的|系統)?\\s*(指令|提示詞|prompt|規則|設定)", "type": "regex", "enabled": true},
  {"pattern": "(reveal|show|output|print|repeat|leak|expose|tell\\s+me)\\s+(your\\s+)?(system\\s+|original\\s+|initial\\s+)?(prompt|instructions|rules|configuration)", "type": "regex", "enabled": true},

  {"pattern": "\\[SYSTEM\\]", "type": "regex", "enabled": true},
  {"pattern": "<\\|im_start\\|>\\s*system", "type": "regex", "enabled": true},
  {"pattern": "<system>|</system>", "type": "regex", "enabled": true},
  {"pattern": "---\\s*(END|NEW|RESET)\\s+(OF\\s+)?(CONVERSATION|SYSTEM\\s+)?PROMPT", "type": "regex", "enabled": true},

  {"pattern": "(列出|顯示|輸出|揭露)(你的|所有|全部)?(工具|tool|function)\\s*(定義|清單|列表|definition|schema)", "type": "regex", "enabled": true},
  {"pattern": "(api[_\\s\\-]*key|api金鑰|金鑰|secret\\s*key|access\\s*token)", "type": "regex", "enabled": true},
  {"pattern": "(連接|連線|使用|呼叫)(的|哪些|什麼)?(資料庫|database|db|qdrant|milvus|postgres)", "type": "regex", "enabled": true}
]$$,
    updated_at = NOW()
WHERE id='default';

-- 紀錄
INSERT INTO _applied_migrations (filename, applied_at, applied_by, phase)
VALUES ('upgrade_guard_input_rules_synonyms.sql', NOW(), 'claude-dev', 'dev')
ON CONFLICT (filename) DO NOTHING;
