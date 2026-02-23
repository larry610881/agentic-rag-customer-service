Feature: Token 成本計算
  作為系統管理者
  我希望根據模型定價自動計算 LLM 成本
  以便準確追蹤每次呼叫的花費

  Scenario: 根據定價表計算正確成本
    Given 模型 "claude-sonnet" 的定價為 input 3.0 output 15.0 per 1M tokens
    When 計算 100 input tokens 和 50 output tokens 的成本
    Then estimated_cost 應為 0.00105

  Scenario: 未配置定價時成本為零
    Given 空的定價表
    When 計算 100 input tokens 和 50 output tokens 的成本
    Then estimated_cost 應為 0.0
