Feature: 知識庫建立→上傳→查詢完整流程
  E2E 驗證：建立 KB → 上傳文件 → 觸發處理 → 查詢文件 → 確認資料

  Scenario: 知識庫管理完整流程
    Given 已完成租戶設定

    # Step 1: 建立知識庫
    When 我建立知識庫 "產品 FAQ"
    Then 回應狀態碼為 201
    And 知識庫名稱為 "產品 FAQ"

    # Step 2: 上傳文件
    When 我上傳文件 "policy.txt" 到該知識庫
    Then 回應狀態碼為 201
    And 上傳回應包含 document 和 task_id

    # Step 3: 查詢文件列表
    When 我查詢該知識庫的文件列表
    Then 回應狀態碼為 200
    And 文件列表包含 1 個文件

    # Step 4: 查詢知識庫列表
    When 我查詢知識庫列表
    Then 回應狀態碼為 200
    And 知識庫列表包含 1 個知識庫
