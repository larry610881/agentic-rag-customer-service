Feature: 防護階段三層設定 (Guard Stages: Platform floor / Profile / Tenant / Bot)
    身為系統管理員
    我要為防護階段設定系統底線與預設、方案預設，並讓租戶只能在底線之上加嚴、必要時鎖定特定租戶
    以便沒有任何租戶能把防護調到低於系統底線，且每一次變更（不論誰改）都留下稽核、三通路行為一致

    # --- domain：解析（底線 ∪ 方案 ∪ 租戶加嚴 ∪ bot 加嚴）---

    Scenario: 系統底線的階段不可被任何一層關閉
        Given 平台防護設定 stages 為 "regex_input" 且 required_stages 為 "regex_input,output_guard,abuse_scoring"
        And 租戶 "t1" 的防護覆寫 stages 為 "regex_input"
        When 解析租戶 "t1" 的有效防護（bot 階段為 "regex_input"）
        Then 有效階段應為 "regex_input,output_guard,abuse_scoring"
        And 階段 "output_guard" 的來源應為 "required"

    Scenario: 方案給預設、租戶只能加嚴
        Given 平台防護設定使用預設值
        And 方案 "exhibition" 的防護覆寫 stages 為 "regex_input,output_guard,abuse_scoring"
        And 租戶 "t1" 指定防護方案 "exhibition" 並覆寫 stages 為 "classifier_attack"
        When 解析租戶 "t1" 的有效防護（bot 階段為 "-"）
        Then 有效階段應為 "regex_input,classifier_attack,output_guard,abuse_scoring"
        And 階段 "classifier_attack" 的來源應為 "tenant"

    Scenario: 租戶覆寫省略方案已開的階段時該階段仍生效（不能減）
        Given 平台防護設定使用預設值
        And 租戶 "t1" 的防護覆寫 stages 為 "regex_input"
        When 解析租戶 "t1" 的有效防護（bot 階段為 "-"）
        Then 有效階段應為 "regex_input,classifier_attack,output_guard,abuse_scoring"
        And 階段 "classifier_attack" 的來源應為 "platform"

    Scenario: bot 可在租戶有效值之上再加階段
        Given 平台防護設定使用預設值
        And 方案 "exhibition" 的防護覆寫 stages 為 "regex_input,output_guard,abuse_scoring"
        And 租戶 "t1" 指定防護方案 "exhibition"
        When 解析租戶 "t1" 的有效防護（bot 階段為 "regex_input,output_guard,abuse_scoring,classifier_attack"）
        Then 有效階段應為 "regex_input,classifier_attack,output_guard,abuse_scoring"
        And 階段 "classifier_attack" 的來源應為 "bot"

    Scenario: bot 階段必須是租戶有效值的超集
        Given 平台防護設定使用預設值
        When 以租戶 "t1" 的有效防護驗證 bot 階段 "regex_input,output_guard"
        Then 防護驗證失敗訊息含 "cannot remove"

    Scenario: 租戶被鎖定時忽略租戶與 bot 的覆寫
        Given 平台防護設定使用預設值
        And 方案 "exhibition" 的防護覆寫 stages 為 "regex_input,output_guard,abuse_scoring"
        And 租戶 "t1" 指定防護方案 "exhibition" 並覆寫 stages 為 "classifier_attack" 且被鎖定
        When 解析租戶 "t1" 的有效防護（bot 階段為 "local_classifier"）
        Then 有效階段應為 "regex_input,output_guard,abuse_scoring"
        And 有效防護應為鎖定狀態

    Scenario: 租戶被鎖定時 bot 不得設定自己的防護階段
        Given 平台防護設定使用預設值
        And 租戶 "t1" 指定防護方案 "standard" 且被鎖定
        When 以租戶 "t1" 的有效防護驗證 bot 階段 "regex_input,classifier_attack,output_guard,abuse_scoring,local_classifier"
        Then 防護驗證失敗訊息含 "locked"

    Scenario Outline: 覆寫鍵名、階段名稱與各層允許的鍵必須合法
        When 以 scope "<scope>" 驗證防護覆寫 <overrides>
        Then 防護驗證結果為 <outcome>

        Examples:
            | scope    | overrides                             | outcome |
            | platform | {"stages": ["regex_input", "nope"]}   | 失敗    |
            | platform | {"required_stages": ["regex_input"]}  | 通過    |
            | profile  | {"required_stages": ["regex_input"]}  | 失敗    |
            | tenant   | {"locked": true}                      | 通過    |
            | profile  | {"locked": true}                      | 失敗    |
            | tenant   | {"stages": "regex_input"}             | 失敗    |
            | tenant   | {"foo": 1}                            | 失敗    |

    # --- provider：快取與 fail-safe ---

    Scenario: 有效防護快取 60 秒，更新後立即失效
        Given 防護設定儲存庫與快取 provider
        When 連續讀取租戶 "t1" 的有效防護 3 次
        Then 防護儲存庫只被讀取 1 輪
        When 系統管理員將租戶 "t1" 的防護覆寫 stages 設為 "local_classifier"
        And 連續讀取租戶 "t1" 的有效防護 1 次
        Then 防護儲存庫只被讀取 2 輪
        And 有效階段應為 "regex_input,classifier_attack,output_guard,abuse_scoring,local_classifier"

    Scenario: 設定儲存庫失效時退回全部階段開啟（fail-safe，防護寧多勿少）
        Given 防護設定儲存庫與快取 provider
        When 防護儲存庫失效並清除快取
        And 連續讀取租戶 "t1" 的有效防護 1 次
        Then 有效階段應為 "regex_input,classifier_attack,output_guard,abuse_scoring,local_classifier"
        And 階段 "regex_input" 的來源應為 "fallback"

    # --- 稽核：任何層寫入都留紀錄；系統管理員對租戶的變更該租戶看得到 ---

    Scenario: 系統管理員對租戶的變更寫稽核並標記來源為平台
        Given 防護設定儲存庫與快取 provider
        When 系統管理員將租戶 "t1" 的防護覆寫 stages 設為 "local_classifier"
        Then 防護稽核應記錄 entity "guard_settings"、entity_id "tenant:t1"、tenant_id "t1"、source "platform"

    Scenario: 系統管理員改平台底線也寫稽核（無租戶歸屬）
        Given 防護設定儲存庫與快取 provider
        When 系統管理員將平台 required_stages 設為 "regex_input,output_guard"
        Then 防護稽核應記錄 entity "guard_settings"、entity_id "platform:*"、tenant_id "-"、source "api"

    Scenario: 租戶端變更紀錄可見平台對自己的防護變更
        Given 機器人 "bot-1" 屬於租戶 "t1"，稽核含一筆 bot 變更與一筆平台對 "t1" 的防護變更
        When 租戶 "t1" 的 "tenant_admin" 查詢 "bot-1" 的變更紀錄（含防護）
        Then 變更紀錄應有 2 筆，其中 guard_settings 那筆的操作者標籤為 "平台"

    # --- 管線：三通路同一份 helper ---

    Scenario Outline: kb 模式的分類器攻擊判定依階段開關決定（web + LINE）
        Given 平台防護設定 stages 為 "<stages>"
        And 一個 kb 模式的 bot，分類器對訊息的判定為攻擊
        When 以 "<channel>" 通路送出訊息
        Then 分類器應被以無 worker 方式呼叫 <calls> 次
        And 通路回覆應為 "<result>"

        Examples:
            | channel | stages                                                   | calls | result |
            | web     | regex_input,classifier_attack,output_guard,abuse_scoring | 1     | 攔截   |
            | web     | regex_input,output_guard,abuse_scoring                   | 0     | 正常   |
            | line    | regex_input,classifier_attack,output_guard,abuse_scoring | 1     | 攔截   |
            | line    | regex_input,output_guard,abuse_scoring                   | 0     | 正常   |

    Scenario Outline: 關閉的階段在管線中不執行（web + LINE）
        Given 平台防護設定 stages 為 "<stages>" 且 required_stages 為 "-"
        And 一個 deep 模式且沒有 worker 的 bot
        When 以 "<channel>" 通路送出訊息
        Then 輸入正則防護被呼叫 <input> 次、異常計分被呼叫 <abuse> 次
        And Agent 收到的階段清單含 output_guard 為 <output>

        Examples:
            | channel | stages                                 | input | abuse | output |
            | web     | regex_input,output_guard,abuse_scoring | 1     | 1     | true   |
            | web     | classifier_attack                      | 0     | 0     | false  |
            | line    | regex_input,output_guard,abuse_scoring | 1     | 1     | true   |
            | line    | classifier_attack                      | 0     | 0     | false  |

    Scenario: web 通路關閉輸出防護時不呼叫輸出檢查
        Given 平台防護設定 stages 為 "regex_input" 且 required_stages 為 "-"
        And 一個 deep 模式且沒有 worker 的 bot
        When 以 "web" 通路送出訊息
        Then 輸出防護被呼叫 0 次

    Scenario: 咽喉點依階段清單跳過輸入與輸出防護
        Given 一個包了 prompt guard 的咽喉點 agent service
        When 以階段清單 "abuse_scoring" 呼叫咽喉點
        Then 咽喉點的輸入防護被呼叫 0 次、輸出防護被呼叫 0 次
        When 以階段清單 "regex_input,output_guard" 呼叫咽喉點
        Then 咽喉點的輸入防護被呼叫 1 次、輸出防護被呼叫 1 次

    Scenario: trace 應含 guard_stages 節點列出有效階段與來源
        Given 平台防護設定 stages 為 "regex_input,classifier_attack,output_guard,abuse_scoring"
        And 一個 deep 模式且沒有 worker 的 bot
        When 以 "web" 通路送出訊息
        Then trace 應含 "guard_stages" 節點且其階段含 "regex_input"

    # --- bot 儲存：超集規則在寫入時就擋 ---

    Scenario: bot 儲存時 guard_stages 依租戶有效值驗證超集
        Given 防護設定儲存庫與快取 provider
        And 一個既有 bot 的更新用例（帶防護 provider）
        When 將 bot guard_stages 更新為 "regex_input"
        Then bot 更新結果應為 error
        When 將 bot guard_stages 更新為 "regex_input,classifier_attack,output_guard,abuse_scoring,local_classifier"
        Then bot 更新結果應為 saved

    # --- API 授權 ---

    Scenario Outline: 防護設定 API 只有系統管理員能寫，租戶只能讀自己的
        Given 已啟動的防護設定測試應用
        And 以租戶 "<tenant>" 角色 "<role>" 的防護憑證
        When 請求防護端點 "<method>" "<path>"
        Then 防護端點回應狀態碼為 <status>

        Examples:
            | tenant | role         | method | path                                              | status |
            | SYSTEM | system_admin | GET    | /api/v1/admin/guard/settings                      | 200    |
            | t1     | tenant_admin | GET    | /api/v1/admin/guard/settings                      | 403    |
            | SYSTEM | system_admin | PUT    | /api/v1/admin/guard/settings/platform             | 200    |
            | SYSTEM | system_admin | PUT    | /api/v1/admin/guard/settings/profiles/exhibition  | 200    |
            | SYSTEM | system_admin | PUT    | /api/v1/admin/guard/settings/tenants/t1           | 200    |
            | t1     | tenant_admin | PUT    | /api/v1/admin/guard/settings/tenants/t1           | 403    |
            | t1     | tenant_admin | GET    | /api/v1/admin/guard/settings/tenants/t1           | 200    |
            | t1     | tenant_admin | GET    | /api/v1/admin/guard/settings/tenants/t2           | 403    |
            | t1     | tenant_admin | GET    | /api/v1/guard/effective?bot_id=bot-1              | 200    |
            | t2     | tenant_admin | GET    | /api/v1/guard/effective?bot_id=bot-1              | 404    |

    Scenario: 租戶讀取有效防護會回傳階段、底線、鎖定與來源
        Given 已啟動的防護設定測試應用
        And 以租戶 "t1" 角色 "tenant_admin" 的防護憑證
        When 請求防護端點 "GET" "/api/v1/guard/effective?bot_id=bot-1"
        Then 有效防護回應含 stages、required、locked 與 source_map
