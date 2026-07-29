Feature: LINE 快速道檢索預取 (Retrieval Prefetch)
    身為系統維運者
    我想要在 guard 與意圖分類進行的同時預先以原文檢索
    以便快速道命中時把檢索時間藏進並行區，降低回應延遲

    Scenario: 查詢未改寫時快速道直接採用預取結果
        Given 一個開啟直接檢索的 Worker 且分類器未改寫查詢
        When 系統處理一則 LINE 訊息
        Then 檢索應只執行一次且查詢為原文
        And Agent 應以無工具模式單次生成

    Scenario: 查詢被改寫時丟棄預取以改寫查詢重新檢索
        Given 一個開啟直接檢索的 Worker 且分類器將查詢改寫
        When 系統處理一則 LINE 訊息
        Then 檢索應執行兩次且最後一次查詢為改寫後查詢
        And Agent 應以無工具模式單次生成

    Scenario: Worker 覆寫不同知識庫時丟棄預取重新檢索
        Given 一個開啟直接檢索且綁定不同知識庫的 Worker
        When 系統處理一則 LINE 訊息
        Then 檢索應執行兩次且最後一次使用 Worker 的知識庫
        And Agent 應以無工具模式單次生成

    Scenario: 沒有快速道 Worker 時不啟動預取
        Given 一個未開啟直接檢索的 Worker
        When 系統處理一則 LINE 訊息
        Then 不應執行任何檢索
        And Agent 應以完整工具模式處理

    Scenario: Guard 未通過時預取結果不影響 blocked 回覆
        Given 一個開啟直接檢索的 Worker 且輸入會被 guard 攔截
        When 系統處理一則 LINE 訊息
        Then 不應呼叫 Agent
        And 應回覆 guard 攔截訊息

    Scenario: 預取失敗時回退正常檢索流程
        Given 一個開啟直接檢索的 Worker 且第一次檢索會失敗
        When 系統處理一則 LINE 訊息
        Then 檢索應執行兩次
        And Agent 應以無工具模式單次生成
