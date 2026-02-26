Feature: Document CRUD Integration
  使用真實 DB 驗證文件上傳/列表/刪除 API

  Scenario: 上傳文件成功
    Given 已登入為租戶 "Alpha Corp" 並建立知識庫 "FAQ"
    When 我上傳檔案 "test.txt" 到該知識庫
    Then 回應狀態碼為 201
    And 回應包含 document id 和 task_id

  Scenario: 列出知識庫的文件
    Given 已登入為租戶 "Alpha Corp" 並建立知識庫 "FAQ"
    And 該知識庫已有文件 "a.txt"
    And 該知識庫已有文件 "b.txt"
    When 我送出認證 GET 文件列表
    Then 回應狀態碼為 200
    And 回應包含 2 個文件

  Scenario: 刪除文件成功
    Given 已登入為租戶 "Alpha Corp" 並建立知識庫 "FAQ"
    And 該知識庫已有文件 "a.txt"
    When 我刪除該文件
    Then 回應狀態碼為 204
    And 再查詢文件列表為空

  Scenario: 上傳不支援的檔案類型回傳 400
    Given 已登入為租戶 "Alpha Corp" 並建立知識庫 "FAQ"
    When 我上傳檔案 "test.exe" 到該知識庫
    Then 回應狀態碼為 400
