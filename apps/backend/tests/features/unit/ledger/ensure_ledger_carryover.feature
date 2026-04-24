Feature: EnsureLedger 跨月 addon carryover via topup row (T1.2)

  作為平台計費系統
  我希望跨月建新 ledger 時正確繼承上月 addon 餘額（含 deficit 負值）
  以便租戶加值包 / overage 狀態不會因為月初清零而被偷

  Background:
    Given 租戶 "carry-co" 綁定 plan "starter" base_total=10000000

  Scenario: 上月 addon=2M 繼承到本月成為 carryover topup
    Given carry-co 在 2026-03 的 final addon_remaining 為 2000000
    When 建立 carry-co 在 2026-04 的 ledger
    Then carry-co 在 2026-04 應有 1 筆 reason="carryover" 的 topup amount=2000000

  Scenario: 上月 overage deficit 繼承為負 carryover
    Given carry-co 在 2026-03 的 final addon_remaining 為 -1000000
    When 建立 carry-co 在 2026-04 的 ledger
    Then carry-co 在 2026-04 應有 1 筆 reason="carryover" 的 topup amount=-1000000

  Scenario: 首次 tenant 建 ledger（無上月）不寫 carryover
    Given carry-co 歷史上沒有任何 ledger
    When 建立 carry-co 在 2026-04 的 ledger
    Then carry-co 在 2026-04 應有 0 筆 carryover topup

  Scenario: 跨年邊界 (1 月繼承前年 12 月)
    Given carry-co 在 2025-12 的 final addon_remaining 為 500000
    When 建立 carry-co 在 2026-01 的 ledger
    Then carry-co 在 2026-01 應有 1 筆 reason="carryover" 的 topup amount=500000

  Scenario: 重複呼叫 EnsureLedger 不應重複寫 carryover
    Given carry-co 在 2026-03 的 final addon_remaining 為 500000
    When 建立 carry-co 在 2026-04 的 ledger
    And 再次呼叫 EnsureLedger 建立 carry-co 在 2026-04 的 ledger
    Then carry-co 在 2026-04 應有 1 筆 reason="carryover" 的 topup amount=500000
