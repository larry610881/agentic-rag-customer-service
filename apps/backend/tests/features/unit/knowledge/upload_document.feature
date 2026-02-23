Feature: Upload Document
  作為租戶，我可以上傳文件到知識庫以供 RAG 使用

  Background:
    Given 一個已存在的知識庫

  Scenario: 成功上傳 TXT 文件
    When 上傳一個 TXT 文件 "guide.txt" 到知識庫
    Then 文件狀態為 "pending"
    And 文件綁定到正確的知識庫和租戶

  Scenario: 成功上傳 PDF 文件
    When 上傳一個 PDF 文件 "manual.pdf" 到知識庫
    Then 文件狀態為 "pending"
    And 文件綁定到正確的知識庫和租戶

  Scenario: 成功上傳 DOCX 文件
    When 上傳一個 DOCX 文件 "report.docx" 到知識庫
    Then 文件狀態為 "pending"
    And 文件綁定到正確的知識庫和租戶

  Scenario: 不支援的檔案類型
    When 上傳一個不支援的檔案 "photo.png" 類型為 "image/png"
    Then 拋出 UnsupportedFileTypeError

  Scenario: 上傳至不存在的知識庫
    When 上傳文件到不存在的知識庫
    Then 拋出 EntityNotFoundError
