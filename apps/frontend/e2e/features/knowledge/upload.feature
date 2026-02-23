Feature: 文件上傳 (Document Upload)
  作為電商平台管理員
  我希望能夠上傳文件至知識庫
  以便 AI 客服能夠根據文件內容回答問題

  Background:
    Given 使用者已登入為 "demo@example.com"

  Scenario: 上傳文件並顯示處理進度
    Given 使用者在知識庫 "商品資訊" 的詳情頁面
    When 使用者點擊上傳文件按鈕
    And 使用者選擇檔案 "product-catalog.pdf"
    And 使用者確認上傳
    Then 應顯示上傳進度
    And 文件狀態應從 "處理中" 變為 "已完成"
    And 文件列表應包含 "product-catalog.pdf"
