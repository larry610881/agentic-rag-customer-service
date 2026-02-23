Feature: Sentiment Detection
  情緒偵測與升級標記

  Scenario: 偵測負面情緒並標記升級
    Given 情緒偵測服務已初始化
    When 用戶發送負面訊息 "你們服務太慢了，我很生氣"
    Then 情緒應為 "negative"
    And 應標記為需升級

  Scenario: 正常情緒不標記升級
    Given 情緒偵測服務已初始化
    When 用戶發送正常訊息 "請問退貨政策是什麼"
    Then 情緒應為 "neutral"
    And 不應標記為需升級
