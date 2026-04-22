Feature: Pricing CRUD 管理
  作為系統管理員
  我希望以 append-only 版本管理 LLM 模型定價
  以便在不破壞歷史 snapshot 的前提下，隨時調整新價格

  Scenario: 建立第一筆 pricing 版本
    Given 尚未有任何 "openai" "gpt-5-mini" 的 pricing 版本
    When 我建立一筆 pricing "openai" "gpt-5-mini" input=0.25 output=2.0 effective_from 為未來時間
    Then 新版本應寫入 repository
    And 新版本的 effective_to 應為 None

  Scenario: 建立新版本會把舊版本的 effective_to 釘死
    Given 已有一筆 "anthropic" "claude-haiku-4-5" pricing 生效中 input=1.0 output=5.0
    When 我建立新版本 "anthropic" "claude-haiku-4-5" input=1.1 output=5.5 effective_from 為 1 分鐘後
    Then 舊版本的 effective_to 應等於新版本的 effective_from
    And 最新生效版本查 at=now+2min 應為 input=1.1

  Scenario: 禁止 effective_from 早於現在
    Given 尚未有任何 "openai" "gpt-5-mini" 的 pricing 版本
    When 我建立一筆 pricing "openai" "gpt-5-mini" input=0.25 output=2.0 effective_from 為 1 分鐘前
    Then 應拋出 ValueError 訊息包含 "effective_from"

  Scenario: note 欄位必填
    When 我建立一筆 pricing "openai" "gpt-5" input=1.25 output=10.0 effective_from 為未來時間 但 note 為空字串
    Then 應拋出 ValueError 訊息包含 "note"

  Scenario: 停用某版本會把 effective_to 設為現在
    Given 已有一筆 "openai" "gpt-5" pricing 生效中
    When 我停用該版本
    Then 該版本的 effective_to 應設為當前時間
    And 查詢 at=now+1min 時應查不到 "openai" "gpt-5" 的生效版本

  Scenario: 列出目前生效 + 排程未生效的版本
    Given 已有一筆 "openai" "gpt-5" pricing 生效中 input=1.25
    And 已有一筆 "openai" "gpt-5" pricing 排程 effective_from 為 1 小時後 input=1.30
    When 我列出所有 pricing 版本
    Then 回傳應包含目前生效版本
    And 回傳應包含排程未生效版本
