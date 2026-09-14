# Idempotency-Key 設計（/agent/chat 對外契約，延續 Issue #94）

> 日期：2026-09-14。狀態：設計待拍板，未開 Issue。
> 對應準則：`restful-api-contract-review` D1（建立／生成型 POST 接受 `Idempotency-Key`，同 key 重送回同結果）。

## 0. 一句話

**Redis 只存「這把 key 的第一次回應快照」，對話與訊息照舊只存 Postgres。** 重送命中快照就直接回，
不碰 DB、不打 LLM、不記帳；快照 24 小時後過期，過期後同 key 重送視為新請求。

## 1. 本專案 Redis TTL 現況（盤點）

沒有全域 TTL 政策，每個用途在寫入當下自己指定 `EX` / `SETEX` / `EXPIRE`，且**全部 fail-open**
（Redis 不可用 → 當作沒有這層，記 warning 繼續跑）。

| 用途 | 檔案 | TTL | 寫法 |
|---|---|---|---|
| 對話鎖（同一對話不可並行） | `infrastructure/concurrency/redis_conversation_lock.py` | 120s | `SET NX EX`，釋放時比對 uuid |
| LINE webhook 事件去重 | `infrastructure/line/redis_webhook_event_deduplicator.py` | 3600s（`line_webhook_dedup_ttl_seconds`） | `SET NX EX`，**與本設計同型** |
| 配額預檢快取 | `application/billing/quota_preflight.py` | 30s | `SET EX` |
| 對話摘要快取 | `infrastructure/conversation/summary_recent_strategy.py` | 3600s（`cache_summary_ttl`） | `SETEX` |
| bot 設定 / 供應商設定快取 | container | 120s / 300s | `SETEX` |
| 登入失敗鎖定 | `infrastructure/auth/redis_login_attempt_tracker.py` | 900s | `INCR` + `EXPIRE` |
| 異常控管分數 | `infrastructure/abuse/redis_abuse_score_store.py` | 依等級 | Lua `EVAL` 原子更新 |
| 通知節流 | `infrastructure/notification/redis_throttle.py` | 依規則 | `SETEX` |
| 機器票 / widget 票 | JWT 本身 | 900s | 非 Redis，只有撤銷狀態在 Redis |

結論：本設計沿用同一套慣例——**per-key TTL、`SET NX EX` 搶佔、fail-open**，不引入新機制。

## 2. 兩個儲存體、兩種責任

```
                 ┌──────────────────────────────┐
  客戶端 ──────▶ │ Redis  idem:{scope}:{key}     │  第一次回應的快照（status + body + fingerprint）
   重送同 key    │ TTL 24h；處理中標記 TTL 130s   │  過期即消失，不需清理作業
                 └──────────────────────────────┘
                              │ 第一次（未命中）才往下走
                              ▼
                 ┌──────────────────────────────┐
                 │ Postgres conversations /      │  唯一事實來源，和今天完全一樣
                 │ messages / usage ledger       │  重送命中快照時完全不會碰到
                 └──────────────────────────────┘
```

- **對話不進 Redis**。不做雙寫、不做「Redis 先寫再回填 DB」；DB 的寫入路徑一行都不改。
- 快照存的是 **HTTP 回應**（狀態碼 + `ChatResponse` JSON），不是 domain 物件。重送時原樣回，
  再加一個標頭 `Idempotent-Replayed: true` 讓客戶端／log 分得出來。
- Redis 過期或被清掉 → 同 key 重送會再跑一次。**這是接受的殘餘風險**，與 LINE 去重（1 小時）同級；
  準則 D1 也明講「key 過期不在保證內」。

## 3. 流程

```
POST /api/v1/agent/chat
Idempotency-Key: 8f1c…（客戶端 UUID v4）

1. 沒帶標頭 → 完全照舊（相容既有 web 前端與已接入的客戶端）
2. 格式檢查：1–128 字元、可見 ASCII → 否則 400 invalid_idempotency_key
3. scope = tenant_id + principal + endpoint
     principal：api_client 用 client_id；人類用 user_id
     endpoint ：agent.chat（串流另一個 scope，見 §7）
   fingerprint = sha256(canonical JSON of ChatRequest)
4. SET idem:{scope}:{key} {state:"in_progress", fp} NX EX 130
     成功 → 我方認領，執行原本 handler
        ├─ 2xx → SET 同 key {state:"done", fp, status, body} EX 86400
        ├─ 4xx 業務錯（403/422/429/402）→ DEL key（不快取錯誤，讓客戶端修正後可重用 key）
        └─ 例外 / 5xx / 逾時 → DEL key（客戶端重送會真的重跑）
     失敗（key 已存在）→ GET
        ├─ fp 不同           → 422 idempotency_key_reused（同 key 不同 body）
        ├─ state=in_progress → 409 idempotency_in_progress + Retry-After: 1
        └─ state=done        → 回快照 status/body + Idempotent-Replayed: true
5. Redis 任何錯誤 → warning `idempotency.redis_unavailable`，照舊執行（fail-open）
```

**為什麼處理中標記只給 130 秒**：worker 在 handler 中途被殺（Cloud Run 縮容、OOM），
沒機會 DEL；130s > 請求逾時 30s 也 > 對話鎖 120s，之後 key 自然消失，客戶端重送可再跑。
成功後才換成 24 小時。

**與對話鎖的關係**：同 key 的並行重送在第 4 步就被 409 擋掉，到不了鎖；不同 key 打同一對話仍走
既有鎖 → busy 話術，行為不變。

**記帳**：重送命中快照時 handler 不執行，`record_usage` 自然不會跑第二次。這正是 D1 要保證的
「下游只呼叫一次」。

## 4. Key 與 Value

```
key   : idem:{tenant_id}:{principal}:{endpoint}:{Idempotency-Key}
value : {"v":1,"state":"done","fp":"<sha256>","status":200,"body":{...ChatResponse...},"at":"<iso>"}
```

- scope 綁身份：A 金鑰的 key 永遠打不到 B 金鑰的快照（多租戶隔離）。
- `body` 就是 `ChatResponse.model_dump()`，含 `conversation_id`、`conversation_created`、
  `structured_content.output`，重送拿到的和第一次完全一樣（`conversation_created` 也一樣是 true，
  因為那是「第一次那輪」的事實）。
- 大小估計：一則回應 2–10 KB；24h × POC 流量 << 1 MB。Upstash 免費額度內。
- Redis 若設 `allkeys-lru` 可能提前逐出，效果同過期；不需要為此改設定。

## 5. DDD 落點

| 層 | 檔案 | 內容 |
|---|---|---|
| Domain | `domain/shared/idempotency.py` | `IdempotencyStore` Protocol：`claim(key, fp, ttl) -> ClaimResult`、`complete(key, status, body, ttl)`、`release(key)`；`IdempotencyRecord` dataclass；三個例外 `IdempotencyKeyReused`、`IdempotencyInProgress` |
| Application | `application/shared/idempotency_guard.py` | `IdempotencyGuard.run(scope, key, fingerprint, handler)`：§3 的第 4–5 步，**通路無關**，任何建立型 use case 入口都能包 |
| Infrastructure | `infrastructure/idempotency/redis_idempotency_store.py` | `SET NX EX` / `GET` / `DEL`，RedisError → fail-open；與 `redis_webhook_event_deduplicator.py` 同風格 |
| Interfaces | `interfaces/api/idempotency.py` | FastAPI dependency：讀標頭、驗格式、算 fingerprint、組 scope；`agent_router.agent_chat` 用 `guard.run(...)` 包住原本 body |
| Interfaces | `interfaces/api/errors.py` | 新 code：`invalid_idempotency_key`(400)、`idempotency_key_reused`(422)、`idempotency_in_progress`(409) |
| Config | `config.py` | `idempotency_ttl_seconds=86400`、`idempotency_in_progress_ttl_seconds=130` |
| Container | `container.py` | `idempotency_store`（Singleton，共用 `redis_client`）、`idempotency_guard` |

不加 migration、不改 ORM。`[no-migration]`。

## 6. 測試（BDD 先行）

`tests/features/unit/interfaces/idempotency.feature`，store 用記憶體假件（專案沒裝 fakeredis）：

1. 帶 key 第一次 → handler 執行一次、回 200、快照寫入（TTL 86400）
2. 同 key 同 body 重送 → handler 不執行、body 逐欄相同、`Idempotent-Replayed: true`
3. 同 key 不同 body → 422 `idempotency_key_reused`
4. 同 key 處理中 → 409 + `Retry-After: 1`
5. handler 拋例外 → key 被釋放，下次重送真的重跑
6. handler 回 403 → key 被釋放
7. 不帶 key → 完全不碰 store
8. store 拋 RedisError → 照常執行、handler 一次、不拋錯
9. 不同 principal 同 key → 各自獨立（隔離）
10. 記帳：重送時 `record_usage` 未被呼叫

整合（tests/integration，真 Redis 可用時跑）：commit 後丟棄回應再以同 key 重送 → DB 只有一筆對話、
`usage_ledger` 只有一列。

## 7. 通路覆蓋聲明（channel-parity 規範要求）

| 通路 | 本期 | 說明 |
|---|---|---|
| `/api/v1/agent/chat`（web 後台、API 客戶端） | ✅ | 廠商整合面，主要目標 |
| `/api/v1/agent/chat/stream` | 下一期 | 快照要存事件序列而非單一 body；重送時整段重播。`IdempotencyGuard` 可直接重用，只差 store 的 value 形狀 |
| widget | 下一期 | 同 guard 包 widget router，scope 的 principal 用 widget 票的 visitor_id |
| LINE | 已有等價機制 | `webhookEventId` 去重（1h）就是平台代客戶端做的 idempotency；長期可把 `RedisWebhookEventDeduplicator` 改為 `IdempotencyStore` 的一個 scope，收斂成一份 |

## 8. 規格文件要補的段落（`docs/agent-chat-api-spec.md`）

- §2 標頭表加 `Idempotency-Key`：選填、UUID v4、建議每則訊息一把、逾時／5xx 重送**帶同一把**。
- §6 錯誤表加三個 code。
- 新增 §6.1「重送語意」：24 小時內同 key 同 body 回同一份回應（含同一個 `conversation_id`），
  並帶 `Idempotent-Replayed: true`；超過 24 小時視為新請求。

## 9. 不做的事（與理由）

- **不用 DB 表存 key**：Redis 掛掉的視窗內退化成今天的行為（可能重複），與專案所有 Redis 用途一致；
  POC 階段不值得為此加表、加清理 cron。若日後要「Redis 掛掉也不重複」再加 `idempotency_keys` 表當第二層。
- **不快取錯誤回應**：客戶端修好 body 後應能用同一把 key 成功，Stripe 也只快取成功。
- **不自動產生 key**：沒帶標頭就是沒有重送保護，不猜。

## 10. 工作量估計

Domain + Application + Infrastructure + dependency + router 接線約 250 行；BDD 10 個 scenario 約 200 行；
文件更新半頁。單人一個工作天內可完成並 push。
