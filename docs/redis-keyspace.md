# Redis Keyspace 與 TTL 一覽

> 2026-09-14（Issue #95）。本專案 Redis 沒有全域 TTL 政策：每個用途在寫入當下自己指定 TTL，
> **全部 fail-open**（Redis 不可用 → 該層視為不存在，記 warning 繼續跑）。數值集中在 `config.py`
> 「Redis TTL」分組，可用環境變數覆寫；機制各自實作，不抽共用 policy 層。
>
> 出事時先用前綴看用量與殘留：`redis-cli --scan --pattern 'idem:*' | wc -l`。

| 前綴 | 用途 | TTL（config 欄位） | 機制 | 不可用時的降級 | 實作 |
|---|---|---|---|---|---|
| `idem:{tenant}:{principal}:{endpoint}:{key}` | Idempotency-Key 回應快照 | 處理中 130s / 完成 86400s（`idempotency_in_progress_ttl_seconds` / `idempotency_ttl_seconds`） | `SET NX EX` → 完成後 `SET EX` 覆寫 | 無重送保護（可能重複） | `infrastructure/idempotency/redis_idempotency_store.py` |
| `conv_lock:{conversation_id}`、`conv_lock:{visitor}:{bot}` | 同一對話不可並行 | 120s（`conversation_lock_ttl_seconds`） | `SET NX EX`，釋放時比對 uuid | 當作拿到鎖 | `infrastructure/concurrency/redis_conversation_lock.py` |
| `line:evt:{webhookEventId}` | LINE webhook 事件去重 | 3600s（`line_webhook_dedup_ttl_seconds`） | `SET NX EX` | 當作第一次（可能重覆回覆） | `infrastructure/line/redis_webhook_event_deduplicator.py` |
| `quota:*` | 租戶配額預檢快取 | 30s（`quota_preflight_cache_ttl_seconds`） | `SET EX` | 每次重算 | `application/billing/quota_preflight.py` |
| `rl:global:*`、`rl:{tenant}:*`、`rl:ip:*`、`rl:abuse:*` | 限流計數 | 60s 視窗 | `INCR` + `EXPIRE` | 放行 | `infrastructure/ratelimit/redis_rate_limiter.py` |
| `abuse:*` | 異常控管分數 / 等級 | 依等級 | Lua `EVAL` 原子更新 | 視為 L0 | `infrastructure/abuse/redis_abuse_score_store.py` |
| `login:fail:*`、`login:lock:*` | 登入失敗鎖定 | 900s（`login_failure_window_seconds` / `login_lockout_seconds`） | `INCR` + `EXPIRE` / `SET EX` | 不鎖定 | `infrastructure/auth/redis_login_attempt_tracker.py` |
| `notify:throttle:*` | 通知節流 | 依規則 | `SETEX` | 不節流 | `infrastructure/notification/redis_throttle.py` |
| `summary:*`、`bot:*`、`provider:*`、`feedback:*` | 快取 | 3600 / 120 / 300 / 60s（`cache_*_ttl`） | `SETEX` | 未命中 | `infrastructure/cache/redis_cache_service.py` |
| refresh / 撤銷狀態 | token 旋轉、改密碼後作廢 | 依票期 | `SET EX` | 不撤銷（fail-open） | `infrastructure/auth/redis_token_stores.py` |

## 判斷口訣

- 只是「數值要能改」→ 放 `config.py` 的 Redis TTL 分組。
- 要「執行期按租戶改」→ 走 DB 表 + 60s 快取（rate limit 已是這個模式）。
- 兩者都不是 → 不要抽共用 policy 層；鎖、去重、快取、計數的降級語意各不相同。

## 對話資料不在 Redis

對話與訊息只存 Postgres。`idem:*` 存的是 HTTP 回應快照，不是 domain 物件；重送命中快照時不碰 DB。
