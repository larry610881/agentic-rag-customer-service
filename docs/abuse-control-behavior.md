# 異常控管行為說明（Abuse Score + Tiered Response）

> 對象：外部串接者、widget 宿主網站、後台維運。對應 Issue #68（P7）。
> 本頁描述 P7a 已上線的行為；P7b–P7d（identify() 協定、挑戰驗證、後台設定、聚合層）另行補充。

## 1. 原則

- **短暫、分級、可解釋、不鎖真人**：分數線性衰減（每分鐘 -1），每一級都有 TTL，到期自動回復。
- **主體優先**：先對「這個人 / 這個 session」計分；聚合層（IP、租戶）只承接，租戶永遠只被保護不被懲罰。
- **回應中性**：被降權時 API 只回 `temporarily_unavailable` 與 `retry_after`，不告知原因。
- **fail-open**：偵測或 Redis 失效時放行並記錄，不讓一次故障變成整租戶客服停擺。
- **可稽核**：每次升級與手動解除都寫入稽核紀錄（後台「稽核紀錄」，entity `abuse_control`）。

## 2. 主體（誰被計分）

| 通路 | 主體 | 最高等級 |
|------|------|----------|
| Widget | 伺服器簽發的 visitor id（票內 `visitor_id`） | L3 |
| API key 客戶 | `X-End-User-Id` header（未帶則 `client_id`） | end_user L3；client L2（永不自動撤銷 key） |
| LINE | channel + userId | L4 |
| 後台登入使用者 | user_id | L2（不冷卻、不封鎖） |

## 3. 訊號與分數（預設值）

| 訊號 | 加分 |
|------|------|
| Guard 規則命中（prompt injection） | +5 |
| 分類器判定純攻擊 | +5 |
| 節奏異常（單一主體每分鐘超過 20 句） | +3（每分鐘最多記一次） |
| 連續無法分流到任何 worker（第 3 句起） | 每句 +1 |
| widget 票的 Origin 與請求不符 | +5 |

門檻：L1 ≥ 3、L2 ≥ 8、L3 ≥ 15、L4 ≥ 30（聚合層，P7d）。

## 4. 各級動作

| 等級 | 動作 | 使用者看到 | HTTP |
|------|------|-----------|------|
| L1 觀察 | 該回合不呼叫工具 / MCP、檢索 top-k 減半、系統提示加固定婉拒指令 | 正常回答或簡短婉拒 | 200 |
| L2 降速（5 分鐘） | 不進 LLM，只回固定文案；該主體速率上限 5 次/分 | 「請稍後再試」 | 200（chat 回固定文案）；超過速率 429 |
| L3 冷卻（15 分鐘） | 停用 chat（web / widget / API / LINE），其他端點正常 | 「AI 助手暫時休息，請稍後再試」 | 429 |
| L4 封鎖（P7d） | 聚合層 1–24 小時，人工或 TTL 解除 | 同上 | 429 |

L3 / L4 的回應：

```http
HTTP/1.1 429 Too Many Requests
Retry-After: 900

{"detail": "temporarily_unavailable", "retry_after": 900}
```

串流端點（`/agent/chat/stream`、`/widget/{code}/chat/stream`）在送出任何事件前就判定，所以同樣收到 429。

## 5. 串接者的處理建議

- 收到 429 時依 `Retry-After` 等待再重試，不要立即重送；連續重送本身會計入節奏異常。
- API 模式請帶 `X-End-User-Id`（你的終端使用者 id）：降權只作用在該終端使用者，不會影響整把 key；未帶時整把 key 共用同一個分數。
- 正常客人夾雜在攻擊流量中不會被鎖出：只有主體自己的分數才影響自己，租戶層級只會切保守模式。
- 監控模式（`ABUSE_CONTROL_MODE=monitor`）只記分、寫稽核，不執行任何動作；預設為 `enforce`。

## 6. 觀測

- `agent_execution_traces.abuse_level`：該回合主體的等級（0–4），後台對話追蹤可篩選。
- 稽核紀錄：`abuse_control` / `escalate`（含等級、分數、訊號、通路）與 `release`。
- 應用 log：`abuse_control.escalated`、`abuse_control.store_unavailable`（fail-open 事件）。
