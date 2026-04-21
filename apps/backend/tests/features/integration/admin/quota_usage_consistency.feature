Feature: 本月額度 total_used_in_cycle 來自 token_usage_records SUM — Route B 不變性

  作為平台系統管理員
  我希望「本月額度」與「Token 用量」兩頁顯示的本月累計用量結構上一致
  以便計費稽核與客服解釋時不會出現兩份互相矛盾的數字

  Background:
    Given admin 已登入並 seed 三個方案
    And 已建立租戶 "sum-co" 綁定 plan "starter"

  Scenario: 多筆不同 category 的 usage — total_used_in_cycle 為所有加總
    Given sum-co 已寫入 1000 tokens 用量 category "rag"
    And sum-co 已寫入 2000 tokens 用量 category "chat_web"
    And sum-co 已寫入 500 tokens 用量 category "embedding"
    When admin 查詢 sum-co 本月 quota
    Then total_used_in_cycle 應為 3500

  Scenario: included_categories 限制計費 category — total_used_in_cycle 仍顯示全部用量
    Given sum-co 設定 included_categories=["rag"]
    And sum-co 已寫入 500 tokens 用量 category "rag"
    And sum-co 已寫入 700 tokens 用量 category "chat_web"
    When admin 查詢 sum-co 本月 quota
    Then total_used_in_cycle 應為 1200
    And base_remaining 應為 9999500

  Scenario: 跨月份 SUM 不互相汙染
    Given sum-co 於 2026-03 已寫入 9999 tokens 用量
    And sum-co 本月已寫入 100 tokens 用量 category "rag"
    When admin 查詢 sum-co 本月 quota
    Then total_used_in_cycle 應為 100
