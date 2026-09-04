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

## 7. 告警與通知（P7c）

通知走既有「通知渠道」（後台 → 平台運維 → 通知渠道），渠道勾選「異常控管告警」即接收：

| 事件 | 觸發 | 節流 |
|------|------|------|
| L3 / L4 升級 | 主體進入冷卻或封鎖 | 同主體同等級依渠道 throttle_minutes |
| fail-open | 分數儲存（Redis）不可用而放行——控管默默失效的唯一線索 | 每租戶 15 分鐘一次，並累計當日次數 |
| 429 / 降速突增 | 每租戶 5 分鐘內速率限制 429 與 L2 觸發合計達 20 次 | 每個 5 分鐘視窗一次 |
| 每日摘要 | 每天 09:15（台北）：各級升級次數、解除次數、fail-open 次數、Top 主體 | — |

- **Teams 為第一通路**：渠道類型 `teams`，`webhook_url` 填 Teams Workflows（Power Automate）「When a Teams webhook request is received」產生的 URL；payload 為 Adaptive Card（`type=message`、`attachments[0].contentType=application/vnd.microsoft.card.adaptive`）。舊版 Office 365 Connector Incoming Webhook 已退場，不支援。
- **Email 為第二通路**：沿用 SMTP 設定；`recipients` 未填時後台顯示「未設定」，發送時跳過並記錄，不會讓通知流程失敗。
- 通知內容不含使用者原文與完整 id：只顯示遮罩後的主體（例 `visitor visi…56`）、通路、等級、原因摘要、剩餘時間與後台連結。
- 單一渠道發送失敗只記 log，不影響其他渠道；「測試發送」端點對 Teams 與 Email 都可用。

## 8. 設定三層與方案（P7c 設定層）

**只有系統管理員能改**；租戶管理員只能在「異常控管狀態」頁看到自己生效中的設定與受控清單。

解析順序：程式預設 → 系統預設（platform）→ 方案（profile，租戶指定，預設 `standard`）→ 租戶微調。每層只存有改的鍵。

| 內建方案 | 說明 |
|----------|------|
| `standard` | 程式預設（門檻 3 / 8 / 15 / 30） |
| `strict` | 門檻 2 / 5 / 10 / 20，冷卻時間加長，每分鐘上限 12 句 |
| `lenient` | 門檻 5 / 12 / 25 / 50，冷卻時間縮短，每分鐘上限 30 句 |
| `monitor` | 只記分不動作（新租戶建議先跑一週） |

可調鍵：模式、啟用、四級門檻（必須遞增）、L2–L4 持續秒數、衰減、每分鐘訊息上限、無法分流免計句數、L2 速率、LINE 冷卻靜默、各訊號加分、各主體最高等級、IP 層開關與白名單。每個數值都有平台硬上限（例：門檻不可調到等於關閉），超出回 422。不開放調整：fail-open、回應不洩漏原因、稽核必寫。

生效設定在程序內快取 60 秒；後台儲存後立即清快取。設定表讀不到時退回程式預設（fail-open）。API：`GET/PUT /api/v1/admin/abuse/settings/*`、`GET /api/v1/admin/abuse/controls`、`POST /api/v1/admin/abuse/controls/release`。

## 9. 聚合層：IP 最後防線與租戶保護（P7d）

- 主體剛進入 L3 時，把 `aggregate_weight`（預設 12）加到兩個聚合層：**IP**（同一來源 IP）與**租戶**。聚合層分數達 L4 門檻（預設 30）才動作。
- **IP 層**：達門檻 → L4 封鎖（預設 1 小時），該 IP 之後的任何新主體（換 visitor、換 API 終端使用者）都被拒絕。每租戶可關閉 IP 層、可設 IP 白名單；LINE 通路沒有 IP，不參與。
- **租戶層永遠只被保護**：達門檻 → 全租戶進入保守模式（不呼叫工具、加婉拒指令）、rate limiter 把全租戶上限減半、發「租戶疑似受攻擊」告警給 Teams。不會拒絕任何人。
- 聚合層的升級同樣寫稽核（訊號 `aggregate`）並依 TTL 自動回復；後台受控清單可看到 `ip` / `tenant` 主體並手動解除。
- 換身分重來的攻擊者：三個主體在同一 IP 先後被冷卻，第四個身分一開始就被 IP 層擋下；正常客人若剛好共用該 IP（公司 NAT），最壞情況是被封鎖一小時，可由系統管理員解除或把該 IP 加入白名單。

