Feature: 點數制計價 (Issue #74 雙軌計價)
    身為系統管理員
    我要方案可以選 token 制（預設）或點數制，點數在記帳當下依方案換算
    以便 token 永遠是事實來源、點數只是換算層，切換方案不重算歷史

    Background:
        Given 平台點數匯率為每點 0.001 美元

    # --- 換算優先序 ---

    Scenario: 模型點數表優先於美元換算
        Given 點數制方案 "pro" 每月 1000 點、預設倍率 1
        And 模型 "openai:gpt-5.1" 設定點數表 輸入每千 10 點、輸出每千 30 點
        When 租戶 "t1" 以模型 "openai:gpt-5.1" 記錄 1000 輸入 500 輸出 tokens 成本 0.05 美元 類別 "chat_web"
        Then 寫入的用量紀錄 points 為 25

    Scenario: 無模型點數表時以美元除以匯率換算
        Given 點數制方案 "pro" 每月 1000 點、預設倍率 1
        When 租戶 "t1" 以模型 "openai:gpt-5.1" 記錄 1000 輸入 500 輸出 tokens 成本 0.0123 美元 類別 "chat_web"
        Then 寫入的用量紀錄 points 為 13

    Scenario: 換算結果無條件進位
        Given 點數制方案 "pro" 每月 1000 點、預設倍率 1
        When 租戶 "t1" 以模型 "openai:gpt-5.1" 記錄 10 輸入 5 輸出 tokens 成本 0.0001 美元 類別 "chat_web"
        Then 寫入的用量紀錄 points 為 1

    # --- 類別倍率 ---

    Scenario: 類別倍率乘上後再無條件進位
        Given 點數制方案 "pro" 每月 1000 點、預設倍率 1
        And 方案 "pro" 類別 "eval_gate" 倍率 0.5
        When 租戶 "t1" 以模型 "openai:gpt-5.1" 記錄 1000 輸入 500 輸出 tokens 成本 0.013 美元 類別 "eval_gate"
        Then 寫入的用量紀錄 points 為 7

    Scenario: 倍率 0 的類別不扣點但仍有 token 紀錄
        Given 點數制方案 "pro" 每月 1000 點、預設倍率 1
        And 方案 "pro" 類別 "auto_classification" 倍率 0
        When 租戶 "t1" 以模型 "openai:gpt-5.1" 記錄 1000 輸入 500 輸出 tokens 成本 0.05 美元 類別 "auto_classification"
        Then 寫入的用量紀錄 points 為 0
        And 寫入的用量紀錄 input_tokens 為 1000

    Scenario: 未列出的類別使用方案預設倍率
        Given 點數制方案 "pro" 每月 1000 點、預設倍率 2
        When 租戶 "t1" 以模型 "openai:gpt-5.1" 記錄 1000 輸入 500 輸出 tokens 成本 0.01 美元 類別 "chat_line"
        Then 寫入的用量紀錄 points 為 20

    # --- 雙軌並行 ---

    Scenario: token 制方案的用量紀錄 points 為 0
        Given token 制方案 "starter"
        When 租戶 "t1" 以模型 "openai:gpt-5.1" 記錄 1000 輸入 500 輸出 tokens 成本 0.05 美元 類別 "chat_web"
        Then 寫入的用量紀錄 points 為 0
        And 寫入的用量紀錄 input_tokens 為 1000

    Scenario: 切換方案只影響之後的用量，不重算歷史
        Given token 制方案 "starter"
        When 租戶 "t1" 以模型 "openai:gpt-5.1" 記錄 1000 輸入 500 輸出 tokens 成本 0.05 美元 類別 "chat_web"
        And 租戶 "t1" 切換到點數制方案 "pro" 每月 1000 點、預設倍率 1
        And 租戶 "t1" 以模型 "openai:gpt-5.1" 記錄 1000 輸入 500 輸出 tokens 成本 0.05 美元 類別 "chat_web"
        Then 第 1 筆用量紀錄 points 為 0
        And 第 2 筆用量紀錄 points 為 50

    Scenario: 記帳寫入推理 token 數
        Given token 制方案 "starter"
        When 租戶 "t1" 記錄含 300 推理 tokens 的用量
        Then 寫入的用量紀錄 reasoning_tokens 為 300

    Scenario: 方案與倍率快取 60 秒
        Given 點數制方案 "pro" 每月 1000 點、預設倍率 1
        When 租戶 "t1" 以模型 "openai:gpt-5.1" 記錄 1000 輸入 500 輸出 tokens 成本 0.01 美元 類別 "chat_web"
        And 租戶 "t1" 以模型 "openai:gpt-5.1" 記錄 1000 輸入 500 輸出 tokens 成本 0.01 美元 類別 "chat_web"
        Then 方案只從資料庫讀取 1 次

    # --- 配額 ---

    Scenario: 點數制配額快照包含月點數、加購點數與已用點數
        Given 點數制方案 "pro" 每月 500 點、預設倍率 1
        And 租戶 "t1" 本月已用 120 點且加購 100 點
        When 計算租戶 "t1" 的配額
        Then 配額快照 billing_mode 為 "points"
        And 配額快照 points_total 為 600、points_used 為 120、points_remaining 為 480

    Scenario: token 制配額快照維持 token 欄位且點數為 0
        Given token 制方案 "starter"
        When 計算租戶 "t1" 的配額
        Then 配額快照 billing_mode 為 "token"
        And 配額快照 points_total 為 0、points_used 為 0、points_remaining 為 0

    Scenario: 點數制自動展延寫入加購點數
        Given 點數制方案 "pro" 每月 500 點、加購包 200 點
        When 對租戶 "t1" 執行自動展延
        Then 寫入的加購紀錄 amount_points 為 200

    # --- 估算 ---

    Scenario: 點數制租戶的估算另回估算點數
        Given 點數制方案 "pro" 每月 1000 點、預設倍率 1
        And 方案 "pro" 類別 "eval_gate" 倍率 0.5
        When 估算租戶 "t1" 類別 "eval_gate" 成本 0.0123 美元
        Then 估算結果 billing_mode 為 "points" 且 est_points 為 7

    Scenario: token 制租戶的估算點數為 0
        Given token 制方案 "starter"
        When 估算租戶 "t1" 類別 "eval_gate" 成本 0.0123 美元
        Then 估算結果 billing_mode 為 "token" 且 est_points 為 0
