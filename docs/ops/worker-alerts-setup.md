# Worker Resilience — GCP Cloud Logging / Monitoring Alert 設定

> 對應 Layer 5 — Worker job structured logs + alert。本檔不自動化（GCP IAM
> 寫權限留 ops 手動），列出在 GCP Console 設一次的步驟。

## 結構化 Log Schema

`apps/backend/src/worker_resilience.py::execute_with_resilience` 在 5 個業務
job（`split_pdf` / `process_document` / `extract_memory` / `classify_kb` /
`run_evaluation`）會 emit 5 種 event：

| Event | 何時 | 重要欄位 |
|---|---|---|
| `worker.job.start` | job 進入 | `job`, `task_id`, `attempt`, `document_id`/`tenant_id` |
| `worker.job.complete` | 成功完成 | `job`, `task_id`, `status="ok"`, `attempt`, `latency_ms` |
| `worker.job.retry` | transient 失敗，arq 將 retry | `job`, `attempt`, `next_attempt`, `defer_seconds`, `error`, `error_msg` |
| `worker.job.permanent_fail` | permanent 失敗（auth / config）— 不 retry | `job`, `task_id`, `attempt`, `error`, `error_msg`, `latency_ms` |
| `worker.job.exhausted` | transient 連續 N 次到達 max_tries | `job`, `task_id`, `attempt`, `error`, `error_msg`, `latency_ms` |

GCP Cloud Run / Cloud Logging 會自動把 structlog JSON 變成 `jsonPayload.<key>`
查詢欄位。

## Logging-based Metric

### `worker_job_failure_rate`（Counter）

**Path:** Logging → Logs-based Metrics → Create Metric

```
resource.type="cloud_run_revision"
resource.labels.service_name="agentic-rag-worker"
( jsonPayload.event="worker.job.permanent_fail"
  OR jsonPayload.event="worker.job.exhausted" )
```

- **Type:** Counter
- **Labels:** `job` (extract from `jsonPayload.job`)
- **Description:** Worker job permanent + exhausted failure count, per job type.

### `worker_job_retry_count`（Counter — 健康指標）

```
resource.type="cloud_run_revision"
resource.labels.service_name="agentic-rag-worker"
jsonPayload.event="worker.job.retry"
```

- 觀察「重試但最終救回來」的健康度。retry 多但 exhausted 少 = 系統正在自癒。

### `worker_job_latency_ms`（Distribution）

```
resource.type="cloud_run_revision"
resource.labels.service_name="agentic-rag-worker"
jsonPayload.event="worker.job.complete"
```

- **Type:** Distribution
- **Field:** `jsonPayload.latency_ms`
- **Labels:** `job`
- **Description:** 成功 job 的 latency 分佈，後續 alert 用 p99 threshold。

## Cloud Monitoring Alert

### Alert 1：失敗率超過 5%（5 min window）

**Path:** Monitoring → Alerting → Create Policy

- **Condition type:** "Metric absence" → 不對 → 改 "Threshold"
- **Metric:** `logging.googleapis.com/user/worker_job_failure_rate`
- **Filter:** rate per 5 minutes
- **Trigger:** `worker_job_failure_rate / (worker_job_failure_rate + complete_count) > 0.05`
  - 簡化版：`worker_job_failure_rate > 5` per 5 min（看實際流量決定數值）
- **Notification:**
  - Email: ops@... + larry@...
  - Slack channel `#alerts-rag`（若已綁定 webhook）

### Alert 2：單一 task 重試超過 3 次後仍失敗

更精準的「user 真的需要介入」訊號（exhausted 才是真失敗，retry 不算）。

- **Metric:** `worker_job_failure_rate`，過濾 `metric.label.event="worker.job.exhausted"`
- **Threshold:** `> 0` over 5 min（任何 exhausted 立即告警）
- **Notification:** 同上

### Alert 3（暫緩）：worker job pending age > 10 min

需要從 arq Redis 拉 `pending_jobs` 列表，本 sprint 不做。後續可：

1. 寫一個 arq cron job `arq_health_metrics`，每分鐘讀 Redis `arq:queue` zset
   找最舊 score → 算 `pending_age_seconds`
2. emit `worker.queue.health` event 含 `oldest_pending_age_s`
3. logging metric + alert

## Verification（每次部署 GCP 後）

```bash
# 1. 確認 worker.job.start 有出現（worker 真的有跑）
gcloud logging read 'resource.type="cloud_run_revision"
  AND resource.labels.service_name="agentic-rag-worker"
  AND jsonPayload.event="worker.job.start"' \
  --limit 5 --format="value(timestamp,jsonPayload.job,jsonPayload.task_id)"

# 2. 看最近 retry 事件（健康度）
gcloud logging read 'jsonPayload.event="worker.job.retry"' \
  --limit 10 --format="value(jsonPayload.job,jsonPayload.attempt,jsonPayload.error)"

# 3. 看最近 exhausted（user 介入點）
gcloud logging read 'jsonPayload.event="worker.job.exhausted"' \
  --limit 10
```

## 非 alert 也要看的 dashboard 建議

- `worker.job.complete` 數量按 `job` group → 看每類 job 的吞吐
- `worker.job.retry` / `worker.job.complete` 比例 → 系統健康度（正常 < 5%）
- `latency_ms` p50/p95/p99 by `job` → 慢化曲線
- `db.slow_query` event count → DB 端慢查詢告警（Layer 4）
- `milvus.connection_retry` event count → Milvus 端不穩告警（Layer 2）

## TODO（後續 sprint）

- [ ] 從 arq Redis 拉 `pending_jobs` 寫 metric → 加 alert
- [ ] Worker job admin UI（前端列出 `processing_task.status='failed'` 並可手動 retry）
- [ ] `gcloud monitoring` Terraform / IaC 化此 alert 設定
