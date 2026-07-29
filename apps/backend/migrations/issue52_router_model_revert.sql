-- Issue #52 E4 回滾 — router_model 退回空值（bot 預設 gpt-5.4）
-- 三輪線上實證 nano 不可行：拒收 temperature=0 與 reasoning_effort='none'、
-- reasoning 燒光 400 tokens 預算輸出空字串、耗時 2.8-4.3s 反而比
-- gpt-5.4 的 1.7s 更慢。Larry 2026-07-29 確認退回。
-- 附帶的程式碼硬化（learn-and-strip / reasoning_effort hint / 分類
-- 空輸出安全網）保留 — 通用防護與 nano 無關。

UPDATE bots
SET router_model = ''
WHERE id = '2feba9a0-47b0-49d2-94ee-494fde39d926';  -- LINE 專用客服（家樂福 POC）
-- 預期影響 row 數：1
