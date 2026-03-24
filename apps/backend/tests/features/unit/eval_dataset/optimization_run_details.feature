Feature: Optimization Run 詳情資料
  Prompt 自動優化 Run 應儲存完整的測試案例詳情，
  並提供進行中 run 的 current_score

  Scenario: 儲存 iteration 時 details 應包含 case_results
    Given 一個包含 3 個測試案例的 eval dataset
    And 一個已完成評估的 iteration result
    When 將 iteration 儲存至 details JSON
    Then details 應包含 case_results 陣列
    And case_results 長度應為 3
    And 每個 case_result 應包含 case_id 和 question 和 score 和 answer_snippet
    And 每個 case_result 應包含 assertion_results 陣列

  Scenario: GetRunUseCase 進行中 run 應回傳 current_score
    Given 一個進行中的 optimization run 在第 3 輪 score 為 0.75
    When 查詢該 run 的詳情
    Then response 應包含 current_score 為 0.75
