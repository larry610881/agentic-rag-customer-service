Feature: Background Task Session 隔離
  Background task 必須從 Container 重新解析 use case，
  避免使用已關閉的 request-scoped session。

  Scenario: 文件上傳的 background task 使用獨立 session
    Given 一個文件上傳端點的 background task callback
    When background task 被觸發時
    Then callback 應從 Container 重新解析 use case 而非使用注入的實例

  Scenario: 批次重處理的 background task 使用獨立 session
    Given 一個批次重處理端點的 background task callback
    When background task 被觸發時
    Then callback 應從 Container 重新解析 use case 而非使用注入的實例

  Scenario: 重處理的 background task 使用獨立 session
    Given 一個重處理端點的 background task callback
    When background task 被觸發時
    Then callback 應從 Container 重新解析 use case 而非使用注入的實例
