Feature: 建立知識庫 (Create Knowledge Base)
    身為租戶管理員
    我想要建立知識庫
    以便存放客服相關的知識文件

    Scenario: 成功建立知識庫
        Given 租戶 "t-001" 已存在
        When 我為租戶 "t-001" 建立名稱為 "商品FAQ" 描述為 "常見商品問題" 的知識庫
        Then 知識庫應成功建立
        And 知識庫名稱應為 "商品FAQ"
        And 知識庫應綁定租戶 "t-001"

    Scenario: 列出租戶的知識庫時應只看到自己的
        Given 租戶 "t-001" 有知識庫 "商品FAQ"
        And 租戶 "t-002" 有知識庫 "退貨政策"
        When 我列出租戶 "t-001" 的所有知識庫
        Then 應只回傳 1 個知識庫
        And 回傳的知識庫名稱應包含 "商品FAQ"
