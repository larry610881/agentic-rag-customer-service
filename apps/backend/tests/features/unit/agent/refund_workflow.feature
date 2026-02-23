Feature: Refund Workflow
  退貨多步驟引導流程

  Scenario: 收集訂單編號
    Given Agent 退貨服務已初始化
    When 用戶發送 "我想退貨"
    Then 回應應要求提供訂單編號

  Scenario: 收集退貨原因
    Given Agent 退貨服務已初始化
    And 退貨流程在收集原因步驟
    When 用戶發送 "ORD-001"
    Then 回應應詢問退貨原因

  Scenario: 完成退貨工單建立
    Given Agent 退貨服務已初始化
    And 退貨流程在確認步驟
    When 用戶發送 "商品有瑕疵"
    Then 回應應包含退貨工單編號
