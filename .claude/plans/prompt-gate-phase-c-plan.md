# Phase C 實作計畫：閘門引擎 + 影子執行 + 逐題報告

> 狀態：待 Larry 確認（2026-08-20）
> 上游：`docs/prompt-gate-spec.md` v1.3（§2/§3.2/§3.4/§4/§13.3/§15）、Issue #54
> 依據：三路程式實況探索（send_message 管線 / eval 子系統 / 設定欄位落點鏈）

---

## 0. 探索結論摘要（影響設計的關鍵事實）

| # | 發現 | 對設計的影響 |
|---|------|------------|
| 1 | bot 實體讀取 100% 集中在 `_load_bot_config()`（`send_message_use_case.py:205` 載入後）；`/chat` 路徑**不走 cache**（`bot:{id}` cache 只在 LINE） | config_override = 在 tenant 歸屬檢查後、cfg 組裝前 `apply_snapshot(bot, snapshot)` **一處注入**，零 cache 污染；紅線＝影子路徑絕不 `bot_repo.save()` |
| 2 | execute 與 execute_stream 是**完整複製分身**，持久化寫入點共 6 處（含 guard 攔截分支也落庫） | test-mode 旗標必須雙路對稱；抽 `_finalize()` 統一收尾避免漏改 |
| 3 | `ValidationEvaluator.validate()` 丟棄 per-run 明細（斷言逐項/回應全文/cost 拿不到）、verdict 只有「全過才 PASS」、`:57` by-index 對齊在子集過濾下會**靜默錯位** | Gate 專用 runner 自建（round 策略 + by case_id 聚合），復用 `Evaluator.evaluate` 與斷言引擎，不硬套 ValidationEvaluator |
| 4 | `/validate` 是同步阻塞、RunManager 純記憶體無孤兒處理、`prompt_opt_runs` 無 status 欄位 | gate run 用**新表 `prompt_gate_runs`**（有狀態生命週期）+ `asyncio.create_task`（定案 8）+ startup 孤兒掃描 |
| 5 | `eval_test_cases` 無 `enabled`、`eval_datasets` 無 `is_platform_base`、UpdateDataset 改不了 bot_id、case 無 update use case | 全部本 phase 補（migration + entity/model/repo/UC/router） |
| 6 | `EstimateCostUseCase` 無 repeats 維度（budget 是**次數**不是金額）；`baseline_cost` = 跑一輪全 case 的成本 | gate estimate 用組合公式（§6），不改造既有 estimate |
| 7 | 非 stream `/chat` **無 trace_id 回傳**；`rag_evaluations.trace_id` 是憑空 uuid4 與 agent trace 脫鉤；非 stream `_persist_agent_trace` 漏傳 message_id | 逐題報告需要 trace → `AgentResponse/ChatResponse` 加 `trace_id` + `trace_nodes`（test-mode 才填）；兩個既有 bug 順手修 |
| 8 | gate 欄位若進 config snapshot 白名單 → 改閘門設定會自我觸發版本 | 六個 gate_* 欄位**不進** `_SCALAR_FIELDS`（治理欄位），並加守衛測試 |
| 9 | dataset case 的 `conversation_history` 現況靠「先打 N 次 /chat 建歷史」（低效且污染） | 新增 `history_override`：test-mode 下直接以題目歷史取代 DB 歷史——同時是 Playground 多輪的地基 |
| 10 | Phase B 的 `usage_context`（header + JWT role 白名單）已是現成授權骨架 | config_override 授權直接掛在同一機制上：**usage_ctx 為 eval 類才接受 override/test_mode，否則 403** |

---

## 1. 範圍與不做

**做**：三層開關欄位、`prompt_gate_runs`、Verdict Engine（硬/軟/預算）、config_override 影子執行 + test-mode 隔離（= Playground 後端）、gate run API + 逐題報告儲存、狀態機接線（validate/publish 分支）、UpdateBot 墊片升級、孤兒 run 處理、eval_* 欄位補齊。
**不做（留後續 phase）**：optimizer 迴圈改造（D）、平台通用集題目 seed（F）、前端全部（E）、回放 pairwise（G）。

## 2. 資料模型（3 支 migration，各走五步流程）

### M1 `add_gate_settings.sql`
```sql
ALTER TABLE bots
  ADD COLUMN IF NOT EXISTS gate_mode           VARCHAR(10)      NOT NULL DEFAULT 'off',
  ADD COLUMN IF NOT EXISTS gate_soft_threshold DOUBLE PRECISION NOT NULL DEFAULT 0.8,
  ADD COLUMN IF NOT EXISTS gate_repeats        INTEGER          NOT NULL DEFAULT 3,
  ADD COLUMN IF NOT EXISTS gate_auto_publish   BOOLEAN          NOT NULL DEFAULT FALSE,
  ADD COLUMN IF NOT EXISTS gate_daily_limit    INTEGER          NOT NULL DEFAULT 20,
  ADD COLUMN IF NOT EXISTS gate_budget_usd     DOUBLE PRECISION NOT NULL DEFAULT 1.0;
ALTER TABLE tenants ADD COLUMN IF NOT EXISTS prompt_gate_enabled BOOLEAN NOT NULL DEFAULT FALSE;
UPDATE tenants SET prompt_gate_enabled = TRUE WHERE id = '00000000-0000-0000-0000-000000000000';
```

### M2 `add_eval_gate_flags.sql`
```sql
ALTER TABLE eval_test_cases ADD COLUMN IF NOT EXISTS enabled BOOLEAN NOT NULL DEFAULT TRUE;
ALTER TABLE eval_datasets  ADD COLUMN IF NOT EXISTS is_platform_base BOOLEAN NOT NULL DEFAULT FALSE;
CREATE INDEX IF NOT EXISTS ix_eval_datasets_bot_id ON eval_datasets (bot_id);
```

### M3 `add_prompt_gate_runs.sql`（spec §3.4 原樣，status: queued|running|completed|error）

## 3. Domain 層（新增 4 檔 + 4 檔加欄位）

| 檔案 | 內容 |
|------|------|
| `domain/prompt_gate/assertion_severity.py` | 26 斷言的 hard/soft 固定映射（hard：4 security + `tool_was_called`/`tool_not_called`/`tool_call_count`/`refused_gracefully`；其餘 soft）+ `resolve_severity(assertion_type, params)` 支援 params `severity` 覆寫 |
| `domain/prompt_gate/verdict.py` | 純函式 Verdict Engine：輸入「case 級聚合（by **case_id**）+ 門檻 + 預算」→ `GateVerdict(passed, fail_reasons[hard_gate/soft_gate/budget_exceeded], hard_failed_cases, soft_pass_rate, unstable_cases)`；case 軟通過沿用 `VALIDATION_THRESHOLDS[priority]`（P0=1.0/P1=0.8/P2=0.6） |
| `domain/prompt_gate/gate_run_entity.py` | `PromptGateRun` entity（spec §3.4 欄位）+ 狀態轉移 guard |
| `domain/prompt_gate/gate_run_repository.py` | interface：`save / find_by_id(tenant) / count_today(bot_id) / mark_orphans_error()` |
| `domain/bot/entity.py` | +6 gate 欄位（**不進 snapshot 白名單**；`config_snapshot` 測試加「gate 欄位不在快照」斷言 + 新增「實體欄位 − 白名單 − 顯式排除清單 = ∅」守衛測試，還 Phase A 的債） |
| `domain/tenant/entity.py` | +`prompt_gate_enabled` |
| `domain/eval_dataset/entity.py` | `EvalTestCase.enabled=True`、`EvalDataset.is_platform_base=False` |
| `domain/eval_dataset/repository.py` | +`find_by_bot(bot_id, tenant_id)`、+`find_platform_base()` |

## 4. 影子執行 + test-mode（= Playground 後端）

### 4.1 SendMessageCommand 加三欄位
```python
config_override: dict | None = None   # draft 快照 overlay（spec §13.3）
test_mode: bool = False               # 隔離旗標（spec §15.2）
history_override: list[dict] | None = None  # [{role, content}] 取代 DB 歷史（多輪題/Playground 地基）
```

### 4.2 注入點與隔離面（探索 #1/#2 的落點）
- overlay：`_load_bot_config` 內 tenant 歸屬檢查**之後**（override 不能繞租戶隔離）、cfg 組裝之前。
- test_mode 攔截（雙路對稱，抽 `_finalize()` 統一）：不寫 conversations/messages（**含 guard 攔截分支**）、不觸發 memory extraction、不 enqueue 線上 eval、trace `finish()` 取 nodes 但**不落庫**、不寫 guard_logs；guard 本身照跑；usage 照記（header 分類）。
- history_override：test_mode 下 `_resolve_history` 直接用 override（不查 DB）。
- 回傳：`AgentResponse` + `ChatResponse` 加 `trace_id`、`trace_nodes`（compact，**僅 test_mode 填充**，剝除 llm_input 全文）。

### 4.3 授權（複用 Phase B 骨架）
`ChatRequest` 加三欄位；`agent_router`：body 帶 override/test_mode 但 `usage_ctx.request_type` 不是 eval 三類（= header 不合法或 role 不足）→ **403**（安全邊界，不 silent）。widget/LINE 不走此 router，天然隔離。

### 4.4 順手修（小而必要）
- `rag_evaluations.trace_id` 憑空 uuid4 → 改用 `AgentTraceCollector.current().trace_id`（修 trace 脫鉤）。
- 非 stream `_persist_agent_trace` 補 `message_id`。

## 5. Gate Run 執行器（application/prompt_gate/gate_run_use_cases.py）

```
StartGateRunUseCase.execute(tenant_id, bot_id, version_id, api_token):
  前置（同步，任一不過即 4xx）：
    tenant.prompt_gate_enabled → 403 / bot.gate_mode != off → 409
    version.status == draft → 409（mark_validating 的 guard 兜底）
    綁題集：find_by_bot 的自訂集 enabled cases ≥ 1 → 422
    日限額：gate_run_repo.count_today(bot_id) < gate_daily_limit → 429
    估算 est_cost（§6）→ 寫入 run 列（超過 gate_budget_usd 直接 422）
  建 run（queued）→ version.mark_validating(run_id) → asyncio.create_task(_execute)
  回 202 {run_id}

_execute（背景，DB 寫入走 independent_session_scope + .provider factory，Phase B 模式）：
  題集 = platform_base 全部 ∪ 自訂集 enabled cases（多 dataset 合併、case_id 冠 dataset 前綴防撞）
  Round 1：全部 case 各 1 次；Round 2..gate_repeats：只跑 P0（定案 7）
  每 case：AgentAPIClient.chat(config_override=快照, test_mode=True,
           history_override=case.conversation_history,
           headers: X-Usage-Category=eval_gate, X-Eval-Run-Id=run_id)
  逐 case 累計 actual_cost，超過 gate_budget_usd → 立即中止 verdict=fail(budget_exceeded)
  斷言：run_assertion + severity 映射；聚合 by case_id → Verdict Engine
  逐題明細寫 details JSONB（§7）→ run completed → version.mark_validation_result(passed)
  例外：run=error、version 退回 draft（fail-open：版本不卡死在 validating）
```

- 影子執行走 **HTTP 回打 `/chat`**（與 `/validate` 先例一致，JWT 從觸發者 request 剝下傳入）——待決點 C-1。
- `AgentAPIClient.chat()` 擴充：`config_override / test_mode / history_override` 三個 payload 欄位 + 回傳 `trace_nodes/trace_id`。

## 6. Estimate（不改造既有 EstimateCostUseCase）

`GateEstimate = baseline_cost × (1 + (repeats−1) × P0_case 占比) + Σ(history 訊息數 × eval_cost_per_call)`，復用 `_calculate_token_breakdown` 與 `_estimate_call_cost`。新端點 `GET /bots/{bot_id}/prompt-gate/estimate?version_id=`，回傳 est_cost / est_calls / 題集組成。

## 7. 逐題報告儲存（spec §4.5）

`prompt_gate_runs.details` JSONB：
```json
{"cases": [{"case_id", "dataset_id", "question", "priority", "rounds": [
  {"round", "response_text(4KB 截斷保頭尾)", "truncated", "assertions":
   [{"type","severity","passed","message"}], "latency_ms","tokens","cost",
   "trace_nodes(compact)"}], "pass_rate","soft_passed","hard_failed","unstable"}]}
```
體積控制：trace_nodes 剝 metadata 中的全文欄位；30 題 × 3 輪 ≈ 數百 KB，可控。

## 8. 狀態機接線與墊片升級

| 位置 | 變更 |
|------|------|
| `PublishConfigVersionUseCase` | 依 gate 分支：`gate off/tenant off` → skipped（現況）；`pending_publish` → pass 發布；`block + draft(fail)` → 409；`warn + draft(fail) + force=true` → VERDICT_FORCED 發布 |
| `bot_config_version_router` | `POST /{vid}/validate`（202）、`publish` body 加 `{force: bool}`、`GET /api/v1/prompt-gate/runs/{run_id}`（run 狀態/報告，3s polling） |
| `UpdateBotUseCase._record_config_version` | 升級：gate 未啟用 → 現行為；**gate_mode ∈ {warn, block} 且版控欄位變更 → 409 導引版本 API**（apply 前先 diff 判斷，需注入 tenant_repo）；非版控欄位照常即時生效 |
| `UpdateBotUseCase` gate 前置 | `gate_mode≠off` 時驗證自訂集 enabled cases ≥ 1（application 層，(b) 類先例 `rag_retrieval_modes`），raise ValidationError |
| `main.py` lifespan | 孤兒清理（startup 一次性，fail-open）：`prompt_gate_runs` status ∈ {queued,running} → error；對應 version status=validating → 退 draft |

## 9. 設定欄位落點鏈（照 eval_depth 樣板，行號見探索紀錄）

- bots 6 欄：entity → model → repo `_to_entity`/save×2 → Create/Update Command+apply → router `_VALID_GATE_MODES` + create/update 驗證 + Create/Update/Response schema + `_to_response`（`_build_update_command` 泛型免改）。値域：mode ∈ {off,warn,block}、threshold ∈ [0,1]、repeats ∈ [1,10]、daily_limit ≥ 0、budget > 0。
- tenants 1 欄：entity → model → repo×2 → UpdateTenantCommand/apply → `PATCH /config` 手寫映射加一行 + TenantResponse。
- LINE bot cache 的 `_bot_to_json/_bot_from_json`：確認序列化方式，gate 欄位屬發布期不需進 LINE cache，但若是全欄位序列化則自動帶上（無害）。

## 10. eval dataset CRUD 補齊

`UpdateEvalDatasetCommand` + router 加 `bot_id`、`is_platform_base`（後者 `system_admin` only）；新 `UpdateTestCaseUseCase` + `PATCH /datasets/{id}/test-cases/{case_id}`（v1 只開 `enabled`）；platform base 集對非 system 租戶唯讀。

## 11. 測試計畫（BDD 先行）

| Feature | 覆蓋 |
|---------|------|
| `gate_verdict.feature` | 判定矩陣全覆蓋：硬過×軟過/軟不過（79.9/80.0 邊界）、硬不過、預算中止、P0 3 輪 2 過、unstable、無軟斷言、severity 覆寫、**case_id 對齊（亂序輸入）** |
| `gate_settings.feature` | 三層開關組合、前置條件（未綁集/全 disabled 不可啟用）、日限額 429、値域驗證 |
| `shadow_execution.feature` | override 授權（usage_ctx 非 eval 類 → 403）、overlay 在 tenant 檢查後、test_mode 六面隔離（含 guard 攔截分支不落庫）、history_override、trace_nodes 回傳、**gate 欄位不進快照守衛** |
| `gate_run_lifecycle.feature` | 202 啟動、validating→pending_publish/draft、block/warn/force 發布分支、背景例外退 draft、孤兒清理 |
| `update_bot_shim.feature`（擴充） | gate on 時版控欄位 409、gate 設定欄位直接生效不產版本 |
| integration | validate→run→publish e2e（mock LLM）、estimate、eval dataset CRUD 新欄位、`/chat` 403/正常 override |

## 12. 實作順序（單 PR 內的 commit 切分）

1. M1/M2/M3 migration + 落點鏈（bots/tenants/eval_*）+ 守衛測試
2. Verdict Engine + severity 映射（純 domain，測試矩陣先行）
3. 影子執行 + test-mode + history_override + `_finalize()` 重構 + 順手修 2 bug
4. `prompt_gate_runs` + StartGateRun/背景 runner + estimate + API
5. 狀態機接線 + 墊片升級 + 孤兒清理
6. eval dataset CRUD 補齊
7. 全量測試 + lint + todolist/journal 收尾

## 13. 待決點（Phase C 內的新決定）

| # | 問題 | 建議 |
|---|------|------|
| C-1 | 影子執行走 HTTP 回打 `/chat` vs in-process 直呼 SendMessageUseCase | **HTTP 回打**：與 `/validate`/optimizer 先例一致、驗的是含 interfaces 層的完整真實路徑、授權/usage 標記機制天然生效；代價是背景 task 需持 JWT（`/validate` 已有剝 token 先例） |
| C-2 | `history_override` 機制（多輪題 + Playground 多輪的共同地基） | **採納**：優化 crescendo 類題從「N 次真打建歷史」變一次到位；Playground 多輪由前端帶 history（伺服器無狀態） |
| C-3 | 順手修兩個 trace bug（eval trace_id 脫鉤、非 stream message_id） | **修**：改動極小，且逐題報告直接依賴 trace 正確性；屬 observability 計畫 1-P1 的一部分 |
| C-4 | gate run 觸發時 estimate 超過 budget 的行為 | **422 直接擋**（不是 warn）：預算是 bot 擁有者自己設的硬上限 |
| C-5 | 「綁題集」判定用「enabled cases ≥ 1」（新欄位）而非「cases ≥ 1」 | 照 spec 定案（enabled 欄位本 phase 就加，判定一步到位） |
