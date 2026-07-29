Feature: 換版啟動暖機 (Startup Warmup)
    身為系統維運者
    我想要在 lifespan 啟動階段預熱外部連線
    以便 Cloud Run 換版後的第一個請求不用付 DB/Milvus/Redis 首連成本

    Scenario: 啟動時並行預熱三項服務
        Given DB、Milvus、Redis 服務皆正常
        When 執行啟動暖機
        Then DB 應被探測一次
        And Milvus 應被探測一次
        And Redis 應被探測一次

    Scenario: 單一服務失敗不擋啟動
        Given Milvus 探測會拋出例外
        When 執行啟動暖機
        Then 暖機應正常返回不拋例外
        And DB 應被探測一次
        And Redis 應被探測一次

    Scenario: 逾時保護不卡死部署
        Given Milvus 探測會永久卡住
        When 執行啟動暖機且逾時上限為 0.2 秒
        Then 暖機應正常返回不拋例外
