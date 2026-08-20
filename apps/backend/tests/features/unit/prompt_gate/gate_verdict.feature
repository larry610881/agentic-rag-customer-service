Feature: Gate Verdict Engine 分層判定
  通過 = 硬閘門 100% AND 軟閘門通過率 ≥ 門檻 AND 成本 ≤ 預算。
  聚合以 case_id 對齊（防子集重跑的靜默錯位）。

  Scenario: 硬過且軟過且預算內 → PASS
    Given 一組 gate 評測結果：硬斷言全過、軟通過率 0.9、成本 0.5
    When 以軟門檻 0.8 與預算 1.0 判定
    Then 判定為 PASS 且無失敗原因

  Scenario: 軟通過率恰等於門檻 → PASS（邊界）
    Given 一組 gate 評測結果：硬斷言全過、軟通過率 0.8、成本 0.5
    When 以軟門檻 0.8 與預算 1.0 判定
    Then 判定為 PASS 且無失敗原因

  Scenario: 軟通過率低於門檻 → FAIL(soft_gate)
    Given 一組 gate 評測結果：硬斷言全過、軟通過率 0.799、成本 0.5
    When 以軟門檻 0.8 與預算 1.0 判定
    Then 判定為 FAIL 且失敗原因含 soft_gate

  Scenario: 任一硬斷言失敗即 FAIL(hard_gate)，軟閘門再高也沒用
    Given 一組 gate 評測結果：1 個 case 硬斷言失敗、軟通過率 1.0、成本 0.1
    When 以軟門檻 0.8 與預算 1.0 判定
    Then 判定為 FAIL 且失敗原因含 hard_gate
    And 硬失敗案例數為 1

  Scenario: 超出預算 → FAIL(budget_exceeded)
    Given 一組 gate 評測結果：硬斷言全過、軟通過率 1.0、成本 1.5
    When 以軟門檻 0.8 與預算 1.0 判定
    Then 判定為 FAIL 且失敗原因含 budget_exceeded

  Scenario: 複合失敗原因同時回報
    Given 一組 gate 評測結果：1 個 case 硬斷言失敗、軟通過率 0.5、成本 2.0
    When 以軟門檻 0.8 與預算 1.0 判定
    Then 判定為 FAIL 且失敗原因含 hard_gate 與 soft_gate 與 budget_exceeded

  Scenario: P0 案例多輪重跑，硬斷言任一輪失敗即硬失敗
    Given P0 案例 "c1" 三輪結果中第二輪硬斷言失敗
    When 聚合該案例
    Then 案例 "c1" 標記為硬失敗

  Scenario: 案例軟通過依 priority 門檻（P2 三輪過兩輪 → 通過且 unstable）
    Given P2 案例 "c2" 三輪結果中軟斷言通過兩輪
    When 聚合該案例
    Then 案例 "c2" 軟通過且標記 unstable

  Scenario: 同樣三輪過兩輪在 P1 門檻下不通過
    Given P1 案例 "c4" 三輪結果中軟斷言通過兩輪
    When 聚合該案例
    Then 案例 "c4" 軟未通過

  Scenario: 無軟斷言的案例不計入軟通過率分母
    Given 一組結果：2 個案例只有硬斷言且全過、1 個案例軟斷言全過
    When 以軟門檻 0.8 與預算 1.0 判定
    Then 判定為 PASS 且軟通過率為 1.0

  Scenario: 聚合以 case_id 對齊而非順序
    Given 三個案例的多輪結果以亂序輸入
    When 聚合全部案例
    Then 每個案例的通過率與自身輪次一致

  Scenario: severity 覆寫——params 將軟斷言升為硬
    Given 案例 "c3" 的 contains_all 斷言 params 帶 severity hard 且失敗
    When 聚合該案例
    Then 案例 "c3" 標記為硬失敗
