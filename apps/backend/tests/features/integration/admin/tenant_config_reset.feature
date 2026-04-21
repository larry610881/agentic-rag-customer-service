Feature: tenant included_categories 支援顯式重置為 NULL — Bug 1+2 修復

  作為平台系統管理員
  我希望能將租戶的 included_categories 從已勾選清單「重置為 NULL (全計入)」
  並且不影響其他我沒動的欄位

  Background:
    Given admin 已登入並 seed 三個方案
    And 已建立租戶 "reset-co" 綁定 plan "starter"

  Scenario: 顯式送 null — 重置為「全計入」
    Given reset-co 當前 included_categories=["rag", "chat_web"]
    When admin PATCH reset-co config 送 included_categories=null
    Then reset-co 的 included_categories 應為 null

  Scenario: 未帶 included_categories 欄位 — 維持既有值
    Given reset-co 當前 included_categories=["rag"]
    When admin PATCH reset-co config 只送 monthly_token_limit=999
    Then reset-co 的 included_categories 仍為 ["rag"]
    And reset-co 的 monthly_token_limit 應為 999

  Scenario: 顯式送空陣列 — 全不計入（POC 免計費）
    Given reset-co 當前 included_categories=null
    When admin PATCH reset-co config 送 included_categories=[]
    Then reset-co 的 included_categories 應為 []
