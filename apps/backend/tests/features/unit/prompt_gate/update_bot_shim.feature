Feature: PUT /bots 版控墊片
  既有 UpdateBot 路徑的向後相容墊片：版控欄位變更透明產生版本，
  非版控欄位維持原行為，靜態檢查失敗整個更新被擋。

  Scenario: 版控欄位變更透明產生 published 版本
    Given 一個既有 Bot 與已注入版本 repo 的 UpdateBotUseCase
    When 透過 UpdateBot 修改 base_prompt
    Then 產生一筆 published 且 verdict 為 skipped 的版本列
    And 版本 changed_fields 包含 base_prompt
    And Bot 已儲存

  Scenario: 非版控欄位變更不產生版本
    Given 一個既有 Bot 與已注入版本 repo 的 UpdateBotUseCase
    When 透過 UpdateBot 修改 widget_welcome_message
    Then 不產生任何版本列
    And Bot 已儲存

  Scenario: 靜態檢查失敗時整個更新被擋
    Given 一個既有 Bot 與已注入版本 repo 的 UpdateBotUseCase
    When 透過 UpdateBot 將 base_prompt 改為含 injection 句式
    Then 更新拋出靜態檢查錯誤
    And 不產生任何版本列
    And Bot 未被儲存

  Scenario: 未注入版本 repo 時行為照舊（向後相容）
    Given 一個既有 Bot 與未注入版本 repo 的 UpdateBotUseCase
    When 透過 UpdateBot 修改 base_prompt
    Then Bot 已儲存
