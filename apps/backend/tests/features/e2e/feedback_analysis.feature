Feature: 回饋分析流程
  E2E 驗證：提交回饋 → 查詢統計 → 查詢趨勢 → 查詢列表

  Scenario: 回饋收集與分析完整流程
    Given 已完成租戶設定並有對話記錄

    # Step 1: 提交正面回饋
    When 我提交回饋 評分 "thumbs_up" 到第 1 則訊息
    Then 回應狀態碼為 201

    # Step 2: 提交負面回饋
    When 我提交回饋 評分 "thumbs_down" 留言 "不夠詳細" 到第 2 則訊息
    Then 回應狀態碼為 201

    # Step 3: 查詢統計
    When 我查詢回饋統計
    Then 回應狀態碼為 200
    And 統計 total 為 2
    And 統計 thumbs_up 為 1

    # Step 4: 查詢回饋列表
    When 我查詢回饋列表
    Then 回應狀態碼為 200
    And 回饋列表包含 2 筆

    # Step 5: 查詢趨勢
    When 我查詢滿意度趨勢
    Then 回應狀態碼為 200
    And 回應為陣列格式
