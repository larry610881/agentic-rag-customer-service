Feature: Ticket Creation
  客服工單工具能建立客服工單

  Scenario: 成功建立客服工單回傳工單 ID
    Given 租戶 "tenant-001" 需要建立工單
    When 建立工單主題為 "商品瑕疵" 描述為 "收到的商品有損壞"
    Then 應回傳成功的工單建立結果
    And 結果應包含工單 ID

  Scenario: 工單包含 tenant_id 和 order_id 關聯
    Given 租戶 "tenant-001" 需要建立與訂單 "ord-001" 相關的工單
    When 建立工單主題為 "訂單問題" 描述為 "訂單遲遲未到"
    Then 應回傳成功的工單建立結果
    And 結果應包含 tenant_id "tenant-001"
    And 結果應包含 order_id "ord-001"
