Feature: Token 用量頁與本月額度頁加總不變性 — Route B + 共用 function

  作為平台系統管理員
  我希望不論 usage 分佈、是否含 cache tokens、或 filter 設定如何變
  兩頁的本月累計用量數字永遠相等（結構上同一份資料）

  # ea7cbb3（S-Ledger-Unification）：本月額度拆雙視角 — 租戶頁 /quota 只顯示
  # total_billable_in_cycle（原 total_used_in_cycle，breaking rename），全用量改由
  # 系統層額度總覽的 total_audit_in_cycle 呈現。不變性改為：
  # Token 用量頁總和 ≡ total_audit_in_cycle；無 filter 時 billable 亦相等。

  Background:
    Given admin 已登入並 seed 三個方案
    And 已建立租戶 "consistency-co" 綁定 plan "starter"

  Scenario: 含 cache tokens 的 usage — 兩頁加總相等
    Given consistency-co 本月寫入 usage input=100 output=50 cache_read=30 cache_creation=20 category "rag"
    When 調用兩個 API 並比對加總
    Then Token 用量頁總和應等於 200
    And 額度總覽 total_audit_in_cycle 應等於 200
    And 本月額度頁 total_billable_in_cycle 應等於 200

  Scenario: included_categories filter 設定後 display 總和仍相等
    Given consistency-co 設定 included_categories=["rag"]
    And consistency-co 本月寫入 usage input=800 output=200 category "rag"
    And consistency-co 本月寫入 usage input=400 output=100 category "chat_web"
    When 調用兩個 API 並比對加總
    Then Token 用量頁總和應等於 1500
    And 額度總覽 total_audit_in_cycle 應等於 1500
    And 本月額度頁 total_billable_in_cycle 應等於 1000

  Scenario: 跨租戶隔離
    Given consistency-co 本月寫入 usage input=700 output=300 category "rag"
    And 已建立租戶 "other-co" 綁定 plan "starter"
    And other-co 本月寫入 usage input=9000 output=999 category "rag"
    When 調用 consistency-co 的兩個 API 並比對加總
    Then Token 用量頁總和應等於 1000
    And 額度總覽 total_audit_in_cycle 應等於 1000
    And 本月額度頁 total_billable_in_cycle 應等於 1000
