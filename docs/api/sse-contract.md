# SSE 串流契約（`/api/v1/agent/chat/stream`、`/api/v1/widget/{short_code}/chat/stream`）

> 2026-09-16（Issue #98，準則 C3）。OpenAPI 無法描述 SSE 事件，本文是事件層契約的唯一來源。
> 非串流替代：`POST /api/v1/agent/chat`、`POST /api/v1/widget/{short_code}/chat`（同一條管線，只差輸出形狀）。

## 傳輸

- `Content-Type: text/event-stream`，UTF-8。請求方式為 POST 帶 JSON body 與 `Authorization`（或 widget 票），
  所以瀏覽器原生 `EventSource` 不適用；用 `fetch` + ReadableStream（web）、`URLSession.bytes(for:)`（iOS 15+）、
  OkHttp `EventSource`（Android）。
- 每個事件的形狀固定為：
  ```
  id: <本串流內遞增序號，從 1 起>
  data: <單行 JSON>
  <空行>
  ```
  **reader 必須以「空行」為事件邊界組裝後才解析 JSON**，不可把網路 chunk 當事件；UTF-8 多位元組字元與 JSON 都可能跨 chunk。
- `id` 在同一次串流內遞增。**帶 `Idempotency-Key` 的串流**會把整段事件存成快照（24 小時、上限 512 KB）：
  同 key 同 body 重送從快照重播（回應標頭 `Idempotent-Replayed: true`），再帶 `Last-Event-ID: <n>` 就只補送 `id > n` 的事件。
  不帶 key 的串流沒有重播，`id` 只能做去重與缺漏偵測。
- 終止：收到 `done` 事件即結束；連線在沒有 `done` 的情況下結束視為失敗（EOF 不等於成功）。

## 事件型別（`data.type`）

未知型別一律忽略（伺服器可能新增）。

| type | 說明 | 主要欄位 |
|---|---|---|
| `status` | 管線階段（trace 節點） | `status`（如 `react_thinking`、`llm_generating`）、`node_id`、`ts_ms` |
| `token` | 答案增量文字 | `content` |
| `tool_calls` | 本輪呼叫的工具（非 debug 時不含 reasoning） | `tool_calls[{tool_name, label, reasoning}]` |
| `sources` | 檢索來源（bot 關閉 show_sources 時不送） | `sources[{document_name, content_snippet, score, chunk_id, …}]` |
| `contact` | 轉人工聯絡按鈕 | `contact{label, url, type}` |
| `structured_output` | json bot：已解析的結構化答案 | `output`、`display_text` |
| `structured_output_failed` | json bot：模型輸出不符 schema | `error` |
| `retrieval` | 快速道 / kb 檢索統計 | `top_score`、`chunk_count`、`threshold`、`miss` |
| `guard_blocked` | 防護攔截（只有 admin 角色收得到） | `block_type`、`rule_matched`、`replacement` |
| `message_id` | assistant 訊息已持久化 | `message_id` |
| `conversation_id` | 本輪對話 id 與是否新建 | `conversation_id`、`conversation_created` |
| `done` | **終止事件**（帶 `node_id` 的 `done` 是 trace 節點狀態，不是終止；終止的 `done` 沒有 `node_id`） | `trace_id`（可選） |
| `error` | 管線失敗，之後仍會送終止的 `done` | `message` |

內部事件 `usage`、`config_version`、`config_hash` 不下發客戶端。

## 與非串流回應的對應

拼接所有 `token.content` = 非串流的 `answer`；`structured_output.output` = `structured_content.output`；
`sources` 事件 = `structured_content.sources`；`conversation_id` 事件 = `conversation_id` + `conversation_created`。
