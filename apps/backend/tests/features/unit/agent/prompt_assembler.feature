Feature: System Prompt 分層組裝
  作為系統，我需要根據提供的 base_prompt、mode_prompt 和 Bot 自定義指令組裝分層的系統提示詞

  Scenario: 組裝包含 base_prompt 和 mode_prompt
    Given base_prompt 為 "你是專業客服助手"
    And mode_prompt 為 "使用 Router 模式回答"
    And 沒有自定義 Bot 提示詞
    When 組裝系統提示詞
    Then 結果應包含 "你是專業客服助手"
    And 結果應包含 "使用 Router 模式回答"

  Scenario: 組裝包含自定義 Bot 提示詞
    Given base_prompt 為 "你是專業客服助手"
    And mode_prompt 為 "使用 Router 模式回答"
    And 自定義 Bot 提示詞為 "你是窩廚房的客服小助手"
    When 組裝系統提示詞
    Then 結果應包含 "你是專業客服助手"
    And 結果應包含 "使用 Router 模式回答"
    And 結果應包含 "你是窩廚房的客服小助手"
    And 結果應包含 "自定義指令"

  Scenario: 空白自定義提示詞不影響結果
    Given base_prompt 為 "你是專業客服助手"
    And mode_prompt 為 "使用 ReAct 推理"
    And 自定義 Bot 提示詞為 "   "
    When 組裝系統提示詞
    Then 結果應包含 "你是專業客服助手"
    And 結果不應包含 "自定義指令"

  Scenario: 所有欄位皆為空時回傳空字串
    Given base_prompt 為空
    And mode_prompt 為空
    And 沒有自定義 Bot 提示詞
    When 組裝系統提示詞
    Then 結果應為空字串

  Scenario: 只有 base_prompt 時正常組裝
    Given base_prompt 為 "你是專業客服助手"
    And mode_prompt 為空
    And 沒有自定義 Bot 提示詞
    When 組裝系統提示詞
    Then 結果應包含 "你是專業客服助手"
    And 結果應等於 "你是專業客服助手"
