Feature: Feedback 閉環品質標記
  作為系統，我需要將差評回饋關聯到 RAG 檢索品質

  Scenario: Feedback 可設定 retrieval_quality
    Given 一個已建立的 Feedback
    When 設定 retrieval_quality 為 "low"
    Then Feedback 的 retrieval_quality 應為 "low"

  Scenario: 預設 retrieval_quality 為 None
    Given 一個新建立的 Feedback
    Then Feedback 的 retrieval_quality 應為 None

  Scenario: 差評標記為低品質檢索
    Given 一個 rating 為 "thumbs_down" 的 Feedback
    When 分析檢索品質
    Then 應標記相關 chunks 為低品質
