Feature: 知識庫文件列表
  Background:
    Given 知識庫 "kb-001" 存在

  Scenario: 列出知識庫中的所有文件
    Given 知識庫 "kb-001" 有 2 份已上傳文件
    When 查詢知識庫 "kb-001" 的文件列表
    Then 應回傳 2 份文件

  Scenario: 空知識庫回傳空列表
    When 查詢知識庫 "kb-001" 的文件列表
    Then 應回傳 0 份文件
