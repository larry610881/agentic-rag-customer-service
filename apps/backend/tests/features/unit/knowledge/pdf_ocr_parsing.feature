Feature: PDF OCR 解析 (PDF OCR Parsing)
  為了讓掃描版 PDF 也能被向量化
  身為系統
  我需要透過 OCR 引擎將 PDF 頁面轉為可索引文字

  Scenario: OCR 成功解析掃描版 PDF
    Given 一個純圖像 PDF 的原始位元組（共 2 頁）
    And OCR 引擎已設定
    When 解析該 PDF 檔案
    Then 回傳包含每頁文字的純文字（以換頁符分隔）
    And OCR 引擎被呼叫 2 次

  Scenario: OCR 引擎故障時拋出例外
    Given 一個純圖像 PDF 的原始位元組（共 1 頁）
    And OCR 引擎回傳錯誤
    When 嘗試解析該 PDF 檔案
    Then 拋出 OcrProcessingError

  Scenario: 非 PDF 檔案不走 OCR 路徑
    Given 一個 TXT 檔案內容為 "Hello OCR"
    And OCR 引擎已設定
    When 解析該檔案為 TXT 格式
    Then 回傳純文字 "Hello OCR"
    And OCR 引擎未被呼叫

  Scenario: 空白 PDF 回傳空字串
    Given 一個純圖像 PDF 的原始位元組（共 0 頁）
    And OCR 引擎已設定
    When 解析該 PDF 檔案
    Then 回傳空字串
    And OCR 引擎未被呼叫
