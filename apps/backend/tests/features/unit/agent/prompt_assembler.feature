Feature: System Prompt 分層組裝
  作為系統，我需要根據 Agent 模式和 Bot 設定組裝分層的系統提示詞

  Scenario: Router 模式預設組裝
    Given 沒有自定義 Bot 提示詞
    When 以 "router" 模式組裝系統提示詞
    Then 結果應包含基礎品牌聲音
    And 結果應包含 Router 模式指令
    And 結果不應包含 ReAct 推理策略

  Scenario: ReAct 模式預設組裝
    Given 沒有自定義 Bot 提示詞
    When 以 "react" 模式組裝系統提示詞
    Then 結果應包含基礎品牌聲音
    And 結果應包含 ReAct 推理策略
    And 結果不應包含 Router 模式指令

  Scenario: 包含自定義 Bot 提示詞
    Given 自定義 Bot 提示詞為 "你是窩廚房的客服小助手"
    When 以 "router" 模式組裝系統提示詞
    Then 結果應包含基礎品牌聲音
    And 結果應包含 "你是窩廚房的客服小助手"

  Scenario: 空白自定義提示詞不影響結果
    Given 自定義 Bot 提示詞為 "   "
    When 以 "react" 模式組裝系統提示詞
    Then 結果應包含基礎品牌聲音
    And 結果不應包含 "自定義指令"
