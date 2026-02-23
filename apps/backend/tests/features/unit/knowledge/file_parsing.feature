Feature: File Parsing
  檔案解析服務能正確解析各種格式的文件為純文字

  Scenario: 解析 TXT 檔案
    Given 一個 TXT 檔案內容為 "Hello World"
    When 解析該檔案
    Then 回傳純文字 "Hello World"

  Scenario: 解析 CSV 檔案
    Given 一個 CSV 檔案內容為 "name,age\nAlice,30\nBob,25"
    When 解析該檔案
    Then 回傳包含 "Alice" 和 "Bob" 的合併文字

  Scenario: 解析 PDF 檔案
    Given 一個 PDF 檔案的原始位元組
    When 解析該檔案
    Then 回傳提取的文字內容

  Scenario: 解析 DOCX 檔案
    Given 一個 DOCX 檔案的原始位元組
    When 解析該檔案
    Then 回傳段落文字內容

  Scenario: 解析不支援的格式
    Given 一個不支援格式 "image/png" 的檔案
    When 嘗試解析該檔案
    Then 拋出 UnsupportedFileTypeError
