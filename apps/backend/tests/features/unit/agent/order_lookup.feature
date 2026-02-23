Feature: Order Lookup
  訂單查詢工具能查詢訂單狀態和商品資訊

  Scenario: 查詢已存在訂單回傳狀態和預計送達日期
    Given 訂單 "ord-001" 存在於資料庫中
    When 查詢訂單 "ord-001"
    Then 應回傳成功的 ToolResult
    And 結果應包含訂單狀態 "delivered"

  Scenario: 查詢不存在訂單回傳失敗結果
    Given 訂單 "ord-999" 不存在
    When 查詢訂單 "ord-999"
    Then 應回傳失敗的 ToolResult
    And 錯誤訊息應包含 "not found"

  Scenario: 訂單結果包含商品資訊和價格
    Given 訂單 "ord-001" 存在且包含商品資訊
    When 查詢訂單 "ord-001"
    Then 應回傳成功的 ToolResult
    And 結果應包含商品和價格資訊
