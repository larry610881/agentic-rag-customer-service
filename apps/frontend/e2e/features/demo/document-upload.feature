Feature: Demo 1 — 文件上傳與自動向量化
  作為電商平台管理員
  我希望能夠上傳文件至知識庫並自動向量化
  以便 AI 客服能夠根據文件內容回答問題

  Background:
    Given 使用者已登入為 "Demo Store"

  Scenario: 上傳文件並等待處理完成
    Given 使用者在知識庫 "商品資訊" 的詳情頁面
    When 使用者上傳文件 "test-product.txt"
    Then 應顯示文件處理進度
