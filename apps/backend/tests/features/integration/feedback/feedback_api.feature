Feature: Feedback API Integration
  使用真實 DB 驗證回饋 API（含提交、查詢、統計）

  Background:
    Given 已登入為租戶 "Feedback Corp"
    And 已建立對話和訊息

  Scenario: 成功提交回饋
    When 我送出 POST /api/v1/feedback 評分為 "thumbs_up"
    Then 回應狀態碼為 201
    And 回應包含 rating 為 "thumbs_up"

  Scenario: 提交負面回饋含留言
    When 我送出 POST /api/v1/feedback 評分為 "thumbs_down" 留言 "回答不準確"
    Then 回應狀態碼為 201
    And 回應包含 rating 為 "thumbs_down"
    And 回應包含 comment 為 "回答不準確"

  Scenario: 查詢回饋列表
    Given 已提交回饋 "thumbs_up"
    And 已提交回饋 "thumbs_down"
    When 我送出認證 GET /api/v1/feedback
    Then 回應狀態碼為 200
    And 回應包含 2 筆回饋

  Scenario: 查詢回饋統計
    Given 已提交回饋 "thumbs_up"
    And 已提交回饋 "thumbs_up"
    And 已提交回饋 "thumbs_down"
    When 我送出認證 GET /api/v1/feedback/stats
    Then 回應狀態碼為 200
    And 統計包含 total 為 3

  Scenario: 查詢滿意度趨勢
    When 我送出認證 GET /api/v1/feedback/analysis/satisfaction-trend
    Then 回應狀態碼為 200
    And 回應為陣列

  Scenario: 未認證時拒絕存取
    When 我不帶 token 送出 GET /api/v1/feedback
    Then 回應狀態碼為 401
