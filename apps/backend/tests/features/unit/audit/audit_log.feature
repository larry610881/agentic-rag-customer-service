Feature: 管理端變更稽核 (Audit Log)
    身為資安負責人
    我想要 guard 規則、平台 system prompt、bot / worker 設定、租戶旗標的每次變更都留下誰在何時改了什麼
    以便事故時能沿責任鏈往前追

    Scenario: 只記錄變更欄位並截斷長字串
        Given 稽核紀錄器與可觀察的 repository
        When 記錄 entity "bot" id "b1" 由 before {"a": 1, "b": "x", "c": "same"} 變為 after {"a": 2, "b": "LONG", "c": "same"}
        Then 應寫入 1 筆稽核且 changed_fields 只含 "a" 與 "b"
        And "b" 的 after 應被截斷至 2000 字元以內

    Scenario: 無變更時不寫入
        Given 稽核紀錄器與可觀察的 repository
        When 記錄 entity "bot" id "b1" 由 before {"a": 1} 變為 after {"a": 1}
        Then 不應寫入任何稽核

    Scenario: repository 失敗時 fail-open
        Given 稽核紀錄器且 repository.append 會拋例外
        When 記錄 entity "bot" id "b1" 由 before {"a": 1} 變為 after {"a": 2}
        Then 不應拋出例外

    Scenario: 更新 guard 規則留下稽核
        Given guard 規則目前有 2 條 input_rules
        And guard 更新用例已注入稽核紀錄器
        When 管理員 "admin-1" 更新 guard 規則為 1 條 input_rules
        Then 應寫入 entity_type "guard_rules" action "update" actor "admin-1" 的稽核
        And 稽核 changed_fields 應含 "input_rules"

    Scenario: 重設 guard 規則留下稽核
        Given guard 規則目前有 2 條 input_rules
        And guard 重設用例已注入稽核紀錄器
        When 管理員 "admin-1" 重設 guard 規則
        Then 應寫入 entity_type "guard_rules" action "reset" actor "admin-1" 的稽核

    Scenario: 更新平台 system prompt 留下稽核
        Given 平台 system prompt 目前為 "舊提示"
        And 平台 prompt 更新用例已注入稽核紀錄器
        When 管理員 "admin-1" 更新平台 system prompt 為 "新提示"
        Then 應寫入 entity_type "system_prompt" action "update" actor "admin-1" 的稽核
        And 稽核 changed_fields 應含 "system_prompt"

    Scenario: PUT bot 留下稽核並補上版本作者
        Given 一個 base_prompt 為 "舊" 的 bot 與版本 repository
        And bot 更新用例已注入稽核紀錄器
        When 管理員 "admin-1" 將 bot base_prompt 改為 "新"
        Then 應寫入 entity_type "bot" action "update" actor "admin-1" 的稽核
        And 稽核 changed_fields 應含 "base_prompt"
        And 新建的設定版本 author_user_id 應為 "admin-1"

    Scenario: worker 建立、更新、刪除各留一筆稽核
        Given worker 用例已注入稽核紀錄器
        When 管理員 "admin-1" 建立 worker "客服" 再改 prompt 為 "改後" 再刪除
        Then 應依序寫入 entity_type "worker" 的 action "create", "update", "delete" 稽核

    Scenario: 租戶 prompt_gate_enabled 變更留下稽核
        Given 租戶 "t1" 的 prompt_gate_enabled 為 false
        And 租戶更新用例已注入稽核紀錄器
        When 管理員 "admin-1" 將租戶 "t1" 的 prompt_gate_enabled 改為 true
        Then 應寫入 entity_type "tenant" action "update" actor "admin-1" 的稽核
        And 稽核 changed_fields 應含 "prompt_gate_enabled"
