Feature: 診斷規則 CRUD
  身為系統管理員
  我想要管理 RAG 品質診斷規則的門檻與提示文字

  Scenario: 取得診斷規則 — DB 有資料時回傳 DB 規則
    Given DB 中已儲存自訂診斷規則
    When 我取得診斷規則
    Then 應回傳 DB 中的規則

  Scenario: 取得診斷規則 — DB 無資料時回傳預設規則
    Given DB 中沒有診斷規則
    When 我取得診斷規則
    Then 應回傳系統預設規則
    And 單維度規則數量應為 10

  Scenario: 更新診斷規則
    Given DB 中已儲存自訂診斷規則
    When 我更新 context_precision 的門檻為 0.4
    Then 儲存應成功
    And 更新後的規則應反映新門檻

  Scenario: 還原預設規則
    Given DB 中已儲存自訂診斷規則
    When 我還原為預設規則
    Then 規則應回到系統預設值
