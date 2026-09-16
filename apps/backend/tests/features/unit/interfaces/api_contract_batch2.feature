Feature: API 契約改造第二批（Issue #98 步驟 8–11）
  金額固定精度、無型別 object 標記與歷史 structured_content typed、
  X-Client-Version 門檻、SSE 事件序號與 widget 非串流端點。

  Scenario Outline: ApiMoney 固定取整到 6 位小數
    When 以 ApiMoney 序列化 <input>
    Then 金額序列化結果為 <output>

    Examples:
      | input        | output   |
      | 0.1234567891 | 0.123457 |
      | 2            | 2.0      |
      | 0.0000004    | 0.0      |

  Scenario: 對外面的 usage 金額另有字串形式
    When 以 estimated_cost 0.1234567 建立 TokenUsageResponse 並序列化
    Then 序列化含 estimated_cost 0.123457 與 estimated_cost_str "0.123457"

  Scenario: 回應模型的金額欄位都帶精度標記
    When 掃描全部回應模型的金額欄位
    Then 每個名稱含 cost、price、amount 的 number 欄位都有 x-precision

  Scenario: 無型別 object 回應欄位都標記為 opaque 或已 typed
    When 掃描全部回應模型的 object 欄位
    Then 沒有任何未標 x-opaque 且無 properties 的 object 欄位

  Scenario: 對話歷史的 structured_content 與 chat 對齊為 typed
    When 取得 MessageResponse 的 JSON schema
    Then structured_content 引用 HistoryStructuredContent 且含 contact、sources、output

  Scenario Outline: X-Client-Version 門檻
    Given 最低客戶端版本設定為 "<min>"
    When 帶 X-Client-Version "<header>" 打健康檢查
    Then 狀態碼為 <status>

    Examples:
      | min   | header  | status |
      | (none) | 1.0.0   | 200    |
      | 1.2.0 | 1.2.0   | 200    |
      | 1.2.0 | 1.10.0  | 200    |
      | 1.2.0 | 1.1.9   | 426    |
      | 1.2.0 | (none)  | 200    |
      | 1.2.0 | garbage | 200    |

  Scenario: 低於門檻的 426 回應帶穩定 code
    Given 最低客戶端版本設定為 "2.0.0"
    When 帶 X-Client-Version "1.0.0" 打健康檢查
    Then 錯誤 body 的 code 為 "client_upgrade_required" 且帶 min_client_version

  Scenario: SSE 每個事件帶遞增 id
    When 把三個事件經 sse_frame 編碼
    Then 三個 frame 依序帶 id 1、2、3 且以空行結尾

  Scenario: widget 有非串流的 chat 端點
    When 檢查 widget_router 的路由
    Then 存在 POST "/{short_code}/chat" 且回應模型為 WidgetChatResponse
