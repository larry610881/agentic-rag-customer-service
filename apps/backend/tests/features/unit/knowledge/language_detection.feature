Feature: Language Detection
  偵測文件語言以便後續處理

  Scenario: 偵測中文文字
    Given 一段中文文字
    When 執行語言偵測
    Then 偵測結果應為 "zh-cn"

  Scenario: 偵測英文文字
    Given 一段英文文字
    When 執行語言偵測
    Then 偵測結果應為 "en"

  Scenario: 無法辨識時回傳 unknown
    Given 一段無法辨識語言的文字
    When 執行語言偵測
    Then 偵測結果應為 "unknown"
