Feature: 文件上傳 (Document Upload)
  作為電商平台管理員
  我希望能夠上傳文件至知識庫
  以便 AI 客服能夠根據文件內容回答問題

  Background:
    Given 使用者已登入為 "Demo Store"

  Scenario: 知識庫詳情頁顯示上傳區域
    Given 使用者在知識庫 "商品資訊" 的詳情頁面
    Then 應顯示文件上傳區域
    And 應顯示文件列表或空狀態
