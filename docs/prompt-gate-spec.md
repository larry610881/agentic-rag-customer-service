# 規劃書：Prompt 發布閘門 × Prompt 優化整合 × Eval Token 分流

> 狀態：v1.2 待 Larry 確認（2026-08-20）
> v1.1 增補（依 Larry 08-20 討論）：§13 版本化升級為 **Bot 設定整包版控**（取代 §3.1 的 prompt-only 快照）、§14 發布後效果驗證（數據輔助判斷「有沒有變好」）、待決點 10–13。§13/§14 與 §3.1/§6.1/§6.5 衝突處以 §13 為準。
> v1.2 增補：§15 儲存前對照測試 Playground（side-by-side 前後版本聊天室 + 雙執行軌跡 DAG）、待決點 14；計費定案改為租戶自付（§7、待決 3）。
> v1.3（08-20 定案完成）：**14 項待決全部定案**（#1=B 人工發布、#14=獨立 playground 分類）；增補 §4.5 gate run 報告逐題可展開（回應 + DAG）、§15 Playground 隨用隨選 + token 開支備註。
> 需求來源：`docs/prompt-gate-requirement-brief.md`；背景：`docs/observability-maturity-upgrade-plan.md` 第二項 P3
> 本文件 = 階段一交付物。**經確認前不動任何程式碼。**

---

## 0. 事實校正（brief 假設 vs 程式實況）

規劃前先對齊事實，以下落差已納入設計：

| # | brief 敘述 | 程式實況 | 對設計的影響 |
|---|-----------|---------|------------|
| 1 | 斷言引擎 32 種 | 實際 26 種（`assertions.py` 26 個 `@register`） | 硬/軟分類表以 26 種為準（§4.3） |
| 2 | 驗證「沿用 arq worker」 | `/validate` 是**同步阻塞** HTTP 端點；優化 run 用 `asyncio.create_task`（`run_use_cases.py:101`），arq 裡沒有任何 prompt optimizer job | 閘門驗證的執行機制需選擇 → 待決點 8 |
| 3 | `_security_base.yaml` auto-include | 沒有自動注入，是 YAML 手寫 `includes:`；DB 的 `eval_datasets.include_security` 欄位**全 repo 無消費端（空殼）** | 平台通用集強制注入要新做（§5.3），順手處置空殼欄位 |
| 4 | N 次重跑「預設 N=3」 | `/validate` 預設 `repeats=5`；閾值寫死 `VALIDATION_THRESHOLDS`（P0=1.0/P1=0.8/P2=0.6），非 bot 級可調 | 新增 bot 級 `gate_repeats` / `gate_soft_threshold`（§3.2） |
| 5 | 分層判定（硬 100% AND 軟 ≥80% AND 成本 ≤ 預算） | `ValidationEvaluator` 目前只有「全部 case 過才 PASS」，無硬/軟概念、無成本閘門；斷言無 hard/soft 欄位 | 新增 Gate Verdict Engine（§4），復用 ValidationEvaluator 的重跑聚合 |
| 6 | rollback「已有先例，對齊它」 | 有 **3 套獨立 rollback**（CLI / `RollbackRunUseCase` / 迴圈收尾），且 `RollbackRunUseCase` 用**無白名單的 `setattr(bot, target_field, ...)`**（`run_use_cases.py:639`） | 統一收斂到版本發布 use case（§6.4） |
| 7 | （brief 未提）| **優化迴圈中途就把候選 prompt 直接 raw SQL 寫進線上 `bots.base_prompt`**（`runner.py:193` → `db_client.py:55`），且不清 `bot:{id}` cache | 這是閘門要攔的最大破口 → prompt_override 影子執行（§6.1） |
| 8 | （brief 未提）| eval 受測 token 已被記成 `chat_web` 混入正式流量 → **吃租戶配額、觸發 80%/100% 警報、觸發 auto_topup 產生真實 `billing_transactions`**；mutator 的 LLM 呼叫**完全不落帳** | token 分流不只是分類問題，是現行計費正確性 bug（§7） |
| 9 | （brief 未提）| `/runs/{id}`、`/stop`、`/rollback`、`/report`、`/diff`、`/progress` 皆**無 tenant scoping**（跨租戶可讀他人 prompt_snapshot） | 列入 Phase D 補強 |

---

## 1. 總體設計：一套子系統的收斂方式

核心原則：**「prompt 版本狀態機」是唯一寫入 `bots.base_prompt` 的通道**。手動編輯、優化器產出、回滾，全部收斂為「產生一個 draft version → 過閘門 → publish」，publish use case 是唯一落地點（含 cache invalidation）。

```mermaid
graph LR
    A[UI 手動編輯] --> V[CreatePromptVersion<br>含第 0 層靜態檢查]
    B[prompt_optimizer<br>接受的最佳 prompt] --> V
    C[Rollback 選定歷史版本] --> V
    V --> D[draft 版本列]
    D --> G[Gate Run<br>復用 ValidationEvaluator + 斷言引擎<br>+ 新 Verdict Engine]
    G --> P[PublishPromptVersion<br>唯一寫入 bots.base_prompt<br>+ invalidate bot cache]
    G -.失敗.-> D
```

既有零件的角色分配（不重造）：

| 零件 | 在閘門中的角色 |
|------|--------------|
| `assertions.py`（26 種） | 判定引擎的原子單位，新增 hard/soft 分類映射（不改斷言本身） |
| `validation_evaluator.py` | N 次重跑聚合器，原樣復用；verdict 邏輯上移到新 Verdict Engine |
| `Evaluator` / `VALIDATION_THRESHOLDS` | case 級門檻沿用（P0=1.0/P1=0.8/P2=0.6） |
| `eval_datasets` / `eval_test_cases` CRUD | 題集來源，補 `enabled` 欄位與 bot 綁定強化 |
| `EstimateCostUseCase` | 驗證前必跑的成本預檢，原樣復用（新增包裝端點） |
| `AgentAPIClient` | 受測對話管道，加 usage 標記與 prompt_override |
| `RunHistoryClient` / `prompt_opt_runs` | 優化 iteration 歷史照舊；gate run 另建 run 級表（§3.4） |
| `RecordUsageUseCase` / `token_usage_records` | 分流帳本，加 2 個 category + `run_id` 欄位 |
| markdown report（`GetRunReportUseCase`） | gate run 產報告時復用同一產生器 |

---

## 2. 功能開關（三層落地）

| 層級 | 落地方式 | 依據的既有模式 |
|------|---------|--------------|
| 平台層 per-tenant | `tenants.prompt_gate_enabled BOOLEAN NOT NULL DEFAULT FALSE`；`PATCH /tenants/{id}/config`（已有 `require_role("system_admin")`）；admin-tenants 頁加 toggle | `tenants.included_categories` 同表欄位模式 |
| Bot 層 mode | `bots.gate_mode VARCHAR(10) DEFAULT 'off'`（`off\|warn\|block`）等 6 個欄位（§3.2），走 eval_depth 的 12 落點鏈 | `Bot.eval_depth`（entity.py:102） |
| 啟用前置條件 | `UpdateBotUseCase` 內驗證：`gate_mode != 'off'` 時，該 bot 綁定的**自訂集**（非平台通用集）至少 1 個 `enabled=true` 案例，否則 422；UI 鎖定並顯示「須先設定問題集」 | application 層驗證先例（`rag_retrieval_modes` 至少 1 個） |

- system 帳號預設開啟 = seed 將 `SYSTEM_TENANT_ID`（`00000000-0000-0000-0000-000000000000`）的 `prompt_gate_enabled` 設 `true`（migration 內 UPDATE + `seed-data.json` 同步）。前置條件同樣約束。
- 租戶功能可見性：前端以 `GET /tenants/{id}/config`（或登入 payload）取得 flag，關閉時整個閘門 UI 區塊不渲染。

---

## 3. 資料模型變更

### 3.1 新表 `bot_prompt_versions`

```sql
CREATE TABLE bot_prompt_versions (
    id              VARCHAR(36) PRIMARY KEY,
    tenant_id       VARCHAR(36) NOT NULL,
    bot_id          VARCHAR(36) NOT NULL REFERENCES bots(id) ON DELETE CASCADE,
    target_field    VARCHAR(20) NOT NULL DEFAULT 'base_prompt',  -- v1 只有 base_prompt，留擴充
    version_no      INTEGER     NOT NULL,                        -- 每 (bot, target_field) 遞增
    prompt_snapshot TEXT        NOT NULL,
    status          VARCHAR(20) NOT NULL DEFAULT 'draft',
        -- draft | validating | pending_publish | published | rejected
    is_current      BOOLEAN     NOT NULL DEFAULT FALSE,
    source          VARCHAR(20) NOT NULL DEFAULT 'manual',       -- manual | optimizer | rollback | seed
    source_run_id   VARCHAR(36),          -- optimizer run_id（source=optimizer 時）
    gate_run_id     VARCHAR(36),          -- 最近一次 gate run
    gate_verdict    VARCHAR(20),          -- pass | fail | forced | skipped
        -- forced = warn 模式驗證失敗仍強制發布；skipped = gate_mode=off 直接發布
    author_user_id  VARCHAR(36),
    published_at    TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (bot_id, target_field, version_no)
);
CREATE INDEX ix_bpv_bot ON bot_prompt_versions (bot_id, target_field, created_at DESC);
CREATE INDEX ix_bpv_tenant ON bot_prompt_versions (tenant_id);
CREATE UNIQUE INDEX ix_bpv_current ON bot_prompt_versions (bot_id, target_field) WHERE is_current;
```

設計要點：
- **版本列不可變**（append-only，對齊 `prompt_opt_runs` / `token_ledger_topups` 紀律）；「修改 draft」= 建新 draft。
- 「線上版本」= `is_current=true` 那列（partial unique index 保證唯一）；publish 時在同一交易內翻轉 is_current 並寫 `bots.base_prompt`。**`bots.base_prompt` 保留為讀取端的 denormalized 快照**，`send_message_use_case.py:355` 的讀取路徑零改動、零效能影響。
- versioning 無條件生效（補「手動編輯無歷史」的洞），閘門驗證才受三層開關控制。

### 3.2 `bots` 新欄位（沿 eval_depth 模式，共 6 欄）

```sql
ALTER TABLE bots
  ADD COLUMN IF NOT EXISTS gate_mode           VARCHAR(10)      NOT NULL DEFAULT 'off',
  ADD COLUMN IF NOT EXISTS gate_soft_threshold DOUBLE PRECISION NOT NULL DEFAULT 0.8,
  ADD COLUMN IF NOT EXISTS gate_repeats        INTEGER          NOT NULL DEFAULT 3,
  ADD COLUMN IF NOT EXISTS gate_auto_publish   BOOLEAN          NOT NULL DEFAULT FALSE,
  ADD COLUMN IF NOT EXISTS gate_daily_limit    INTEGER          NOT NULL DEFAULT 20,
  ADD COLUMN IF NOT EXISTS gate_budget_usd     DOUBLE PRECISION NOT NULL DEFAULT 1.0;
```

每欄走完整 12 落點鏈：entity → bot_model → migration → repository(load/save×2) → create/update use case → `_VALID_*` 常數 + create/update/response schema（bot_router）→ 前端 type ×3 → bot-detail-form → admin 唯讀頁 → fixture。

### 3.3 `tenants` / `eval_*` / `token_usage_records` 修改

```sql
ALTER TABLE tenants ADD COLUMN IF NOT EXISTS prompt_gate_enabled BOOLEAN NOT NULL DEFAULT FALSE;
UPDATE tenants SET prompt_gate_enabled = TRUE WHERE id = '00000000-0000-0000-0000-000000000000';

ALTER TABLE eval_test_cases ADD COLUMN IF NOT EXISTS enabled BOOLEAN NOT NULL DEFAULT TRUE;
ALTER TABLE eval_datasets  ADD COLUMN IF NOT EXISTS is_platform_base BOOLEAN NOT NULL DEFAULT FALSE;
CREATE INDEX IF NOT EXISTS ix_eval_datasets_bot_id ON eval_datasets (bot_id);

ALTER TABLE token_usage_records ADD COLUMN IF NOT EXISTS run_id VARCHAR(36);
CREATE INDEX IF NOT EXISTS ix_token_usage_records_run_id ON token_usage_records (run_id);
```

- dataset↔bot 綁定維持現有 1 dataset → 0..1 bot（`eval_datasets.bot_id`），一個 bot 可綁多個 dataset（`WHERE bot_id=?`，補 index）。不做 join table——v1 夠用，且不動既有 CRUD。需補：`UpdateDatasetRequest` 加 `bot_id`（現在建立後改不了）＋ dataset UI 加 bot 選擇器。
- `include_security` 空殼欄位：**閘門一律強制注入平台通用集、不看它**；欄位保留給優化 run 路徑後續修活（不在本案 scope，避免偷渡行為變更）。

### 3.4 新表 `prompt_gate_runs`（run 級狀態，補現況缺 run 級表的洞）

```sql
CREATE TABLE prompt_gate_runs (
    id              VARCHAR(36) PRIMARY KEY,          -- run_id
    tenant_id       VARCHAR(36) NOT NULL,
    bot_id          VARCHAR(36) NOT NULL,
    version_id      VARCHAR(36) NOT NULL REFERENCES bot_prompt_versions(id) ON DELETE CASCADE,
    status          VARCHAR(20) NOT NULL DEFAULT 'queued',  -- queued|running|completed|error
    verdict         VARCHAR(10),                             -- pass | fail（completed 才有）
    fail_reasons    JSONB,        -- ["hard_gate","soft_gate","budget_exceeded"] 可複合
    dataset_ids     JSONB NOT NULL,     -- 實際跑的題集快照（平台集 + 自訂集）
    repeats         INTEGER NOT NULL,
    soft_threshold  DOUBLE PRECISION NOT NULL,
    total_cases     INTEGER, hard_failed_cases INTEGER,
    soft_pass_rate  DOUBLE PRECISION, unstable_cases INTEGER,
    est_cost        DOUBLE PRECISION, actual_cost DOUBLE PRECISION,
    input_tokens    BIGINT, output_tokens BIGINT,
    details         JSONB,        -- case 級結果（沿 prompt_opt_runs.details 形狀）
    triggered_by    VARCHAR(36),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    started_at      TIMESTAMPTZ, completed_at TIMESTAMPTZ
);
CREATE INDEX ix_pgr_bot_created ON prompt_gate_runs (bot_id, created_at DESC);
CREATE INDEX ix_pgr_tenant ON prompt_gate_runs (tenant_id);
```

不塞進 `prompt_opt_runs` 的理由：那張表是 iteration 級、無 run 狀態欄位（現況 ListRuns 對 DB run 一律硬編 `"completed"`），gate run 需要 queued/running 生命週期；混用會把既有的形狀問題擴大。Run 列表 UI 以 union 視圖統一呈現三種 run（§8）。

### 3.5 Migration 檔清單（依 `.claude/rules/migration-workflow.md` 流程逐檔套用）

| 檔名 | 內容 | Phase |
|------|------|-------|
| `add_prompt_versions.sql` | §3.1 | A |
| `backfill_prompt_versions.sql` | 每個 bot 現有 `base_prompt` 建 version 1（status=published, is_current, source=seed）；空 prompt 也建（快照="", 語意=用系統預設） | A |
| `add_usage_run_id_and_eval_categories.sql` | §3.3 的 token_usage_records 部分（category 是程式層 enum，DB 無需 DDL；欄名長度確認：`eval_gate`=9、`prompt_optimize`=15，皆 ≤ varchar(20)） | B |
| `add_prompt_gate_runs.sql` | §3.4 | C |
| `add_bot_gate_settings.sql` | §3.2 | C |
| `add_tenant_prompt_gate_flag.sql` | §3.3 tenants 部分（含 system tenant UPDATE） | C |
| `add_eval_case_enabled_platform_flag.sql` | §3.3 eval_* 部分 | C |

每檔附三行檔頭註解（來源/Plan/Issue）、`IF NOT EXISTS`、套用後同步 `infra/schema.sql` 與 `_applied_migrations`。

---

## 4. 狀態機與閘門判定

### 4.1 版本狀態機

```mermaid
stateDiagram-v2
    [*] --> draft : 第0層靜態檢查通過<br>建立版本列（檢查失敗＝400，不產生版本）
    draft --> published : gate_mode=off 直接發布<br>(gate_verdict=skipped)
    draft --> validating : 送驗<br>前置：estimate 顯示 + 日限額未滿
    validating --> pending_publish : 通過 且 auto_publish=false
    validating --> published : 通過 且 auto_publish=true
    validating --> draft : 未通過（gate_run 記 fail<br>UI 顯示失敗案例明細）
    draft --> published : warn 模式強制發布<br>(gate_verdict=forced，需 force=true)
    pending_publish --> published : 人工按發布
    draft --> rejected : 放棄
    pending_publish --> rejected : 放棄
```

- 非法轉移一律 409（如 block 模式下 fail 的 draft 呼叫 publish、published 版本再送驗）。
- `published → 下一版 published`：舊版不改 status，只翻 `is_current`；歷史 published 全部可作 rollback 目標。
- **Rollback**：選任一歷史 published 版本 → 建新版本（source=rollback，快照複製）→ **免重驗直接 publish**（該快照曾過閘門；事故回滾要快）。此為預設，見待決點 9。

### 4.2 第 0 層靜態檢查（同步、毫秒級、免費）

新模組 `application/prompt_gate/static_checks.py`，純函式：

1. **模板變數**：只允許系統已知變數（`{today}`、`{now}`、`{weekday_zh}`，對齊 system-prompt-editor 文件），未知 `{var}` → 擋（防執行期 KeyError/漏洞）。
2. **長度上限**：預設 32,000 字元（約 17k tokens，可常數調整）。
3. **明顯 injection 句式**：黑名單 regex（「忽略以上指示」「ignore previous instructions」「你現在是」等，種子清單復用 `_security_base.yaml` 的攻擊語料反向提煉），命中 → 擋並標示句子。
4. 空 prompt 允許（語意 = 回退系統預設，與現況一致）。

失敗回 400 + 逐項違規明細，**不產生版本列**。

### 4.3 斷言 hard/soft 分類（26 種）

程式層固定映射（`prompt_gate/assertion_severity.py`），斷言引擎本身不動：

| 類別 | 斷言 | 歸屬 |
|------|------|------|
| 資安 | `no_system_prompt_leak`、`no_role_switch`、`no_pii_leak`、`no_instruction_override` | **硬** |
| 行為不變量 | `tool_was_called`、`tool_not_called`、`tool_call_count`、`refused_gracefully` | **硬** |
| 內容/格式/品質/成本（其餘 18 種） | `contains_all`、`contains_any`、`not_contains`、`regex_match`、`language_match`、`max_length`、`min_length`、`starts_with_any`、`latency_under`、`no_hallucination_markers`、`has_citations`、`references_history`、`source_relevance_above`、`response_not_empty`、`sentiment_positive`、`token_count_under`、`cost_under`、`output_tokens_under` | 軟 |

- 個案覆寫：assertion params 可帶 `"severity": "hard"|"soft"`（例：安全題大量使用的 `not_contains` 可升為硬）。平台通用集會用到此覆寫。
- warn 模式下硬斷言失敗照樣醒目標紅（UI 紅色 banner + 逐案標記），僅是不阻擋發布。

### 4.4 Gate Verdict Engine（判定規則，brief §2.3 落地）

```
執行：
  題集 = 平台通用集（is_platform_base=true 全部）∪ bot 自訂集（enabled cases）
  P0 案例跑 gate_repeats 次（預設 3）；P1/P2 跑 1 次（控成本）
  逐 case 累計 actual_cost，超過 gate_budget_usd → 立即中止，verdict=fail(budget_exceeded)

判定：
  hard_pass  = 所有案例的「硬斷言」在其全部重跑中 100% 通過
  case 軟通過 = 該案例軟斷言全過的重跑比例 ≥ VALIDATION_THRESHOLDS[priority]
               （P0=1.0 / P1=0.8 / P2=0.6，沿用現值）
  soft_rate  = 軟通過案例數 / 含軟斷言案例數
  verdict    = PASS iff hard_pass AND soft_rate ≥ gate_soft_threshold AND 未爆預算
```

- 復用 `ValidationEvaluator.validate()` 的重跑聚合與 `unstable` 標記；新增的只是分層 verdict 計算層（純函式，完整單元測試矩陣，§9）。
- 已知技術債順手修：`validation_evaluator.py:57` 以索引位置對齊 case → 改以 case_id 對齊（防順序漂移誤判）。

### 4.5 Gate run 報告：逐題可展開（定案 08-20，配合 #1=B 人工發布）

發布前的 pending_publish 頁面顯示**完整驗證報告**，每一題可展開看「實際回應全文 + 執行軌跡 DAG + 斷言逐項判定」——不只失敗題，通過題也可查（人工發布決策需要看得到證據）。

| 面向 | 做法 |
|------|------|
| 儲存 | `prompt_gate_runs.details` JSONB 的 case 級結果擴充：每次執行存 `response_text`（**截斷上限 4KB，保頭尾**，對齊 observability 計畫 3-P1 的截斷紀律）、`trace_nodes`（compact 版執行節點，餵 DAG 渲染）、`assertions[]` 逐項 pass/fail + 實際值、latency / tokens / cost |
| 體積控制 | 30 題 × N 重跑 × ~數 KB ≈ 每 run 數百 KB JSONB，可控；`trace_nodes` 剝除 llm_input 全文（prompt 是已知的 draft 快照，不重複存） |
| UI | 報告頁：verdict banner（硬/軟/預算三段燈號）→ 題目列表（badge：pass / fail / unstable，硬斷言失敗紅色）→ 展開列：回應全文 + DAG（trace graph 元件改支援吃靜態 nodes，與 live 模式共用）+ 斷言明細 → 底部動作列 [發布] [放棄] [修改重跑] |
| 隱私 | 報告內容 = golden 題集的回應（非真實用戶資料），無 PII 遮罩需求；仍受 tenant scoping 保護 |

---

## 5. 題集雙層設計

### 5.1 平台通用集
- 實體 = SYSTEM tenant 名下、`is_platform_base=true` 的 `eval_datasets`（可多個，如 `security-invariants`、`rag-invariants`）。
- 由 system_admin 在既有 dataset UI 維護（加 platform 標記 toggle，僅 system_admin 可見）——**內容是活的資料**，seed 只是初始值，隨時可增刪調整，下一次 gate run 立即生效。
- **【定案更新 08-20】gate run 預設注入全部 platform base 集的啟用案例，但 bot 級可勾選排除個別題目**（`bots.gate_excluded_cases`，存 case id 清單）：彈性優先，治理改靠完整審計——每次 run 的 `details` 記錄實際執行的每一題與 `excluded_platform_cases` 清單，版本的 gate_run_id 可回溯「當時驗了什麼、跳過什麼」。租戶對平台集仍**不可編輯內容**（列表唯讀顯示「平台通用」badge），只能對自己 bot 做勾選。
- v1 題目內容 = 待決點 6（附錄 A 提供候選清單供圈選）。seed 方式：YAML → `POST /datasets/import` 腳本（或 seed SQL）。

### 5.2 Bot 自訂集
- 既有 `eval_datasets`/`eval_test_cases` CRUD 照舊，補：case `enabled` toggle、dataset `bot_id` 可改（API+UI）。
- 「須先設定問題集」判定 = `EXISTS(自訂集 WHERE bot_id=? AND is_platform_base=false JOIN cases WHERE enabled)` ≥ 1。

### 5.3 已知附帶問題（列入 Phase D）
- `load_from_string` 不支援 `includes`（UI 匯入帶 includes 的 YAML 會失敗）——平台集改走 DB 後此限制影響降低，不擴 scope。
- `_prompt_injection_advanced.yaml`（31 題孤兒檔）是平台通用集的現成素材庫（附錄 A）。

---

## 6. 與 prompt_optimizer 的整合點

### 6.1 影子執行（最關鍵改動）：候選 prompt 不再寫線上表

現況：優化迴圈每輪 `write_prompt` 直接 UPDATE `bots.base_prompt`（線上流量會讀到候選 prompt，且不清 cache）。gate run 驗 draft 也有同樣需求：**用非線上的 prompt 跑對話**。

方案：`POST /api/v1/agent/chat` 新增內部參數 `prompt_override: {target_field, prompt}`：
- 僅在 JWT 具 eval 權限時接受（v1 = `role in (system_admin, tenant_admin)` 且帶 `X-Eval-Run-Id` header；widget/LINE 通路永不接受）——這是新攻擊面，必須測試覆蓋。
- `send_message_use_case` 組 prompt 時以 override 取代 `bot.base_prompt`，其餘流程（RAG、tool、guard）完全一致 → 驗的就是真實執行路徑。
- 優化迴圈改造：`write_prompt` closure 改為只更新記憶體候選值 + 由 `AgentAPIClient` 每次請求帶 override；**迴圈全程不碰 `bots` 表**。`db_client.py` 的 raw SQL write 路徑僅保留給 CLI（標注 deprecated）。

### 6.2 優化器產出 → 版本狀態機
- 迴圈收尾（`runner.py:261` 原「寫回 best prompt」）改為：呼叫 `CreatePromptVersionUseCase(source=optimizer, source_run_id=run_id, snapshot=best_prompt)` 建 draft。
- run 完成的 UI 導引：「優化完成 → 已建立版本 vN（draft）→ 前往驗證/發布」。
- baseline 沒進步（best=iteration 0）則不建版本。

### 6.3 共用件
- estimate：gate 的成本預檢直接包 `EstimateCostUseCase`（`max_iterations=1`、mutator 成本=0、cases=實際注入題集）。
- report：gate run 報告復用 `GetRunReportUseCase` 的 markdown 產生器（改吃 gate run details）。
- run 列表：`ListRunsUseCase` 擴為 union（optimization / validation / gate），`run_type` 欄位補齊（optimization run 現在 details 沒寫 type，順手補寫）。

### 6.4 Rollback 收斂
- `RollbackRunUseCase`（optimizer 的「套用到機器人」）改為：取該 iteration 的 `prompt_snapshot` → 建版本（source=optimizer）→ 走狀態機。**移除無白名單 `setattr`**。
- 版本頁的 rollback（§4.1）為主要路徑。CLI rollback 保留但同樣導向版本 use case。

### 6.5 `PUT /api/v1/bots/{id}` 的 base_prompt 攔截（相容墊片）
- payload 的 `base_prompt` 與現值**相同** → 忽略（bot-detail-form 現在會原值 round-trip，不能破壞）。
- 不同且 `gate_mode=off` → 透明代建版本並發布（行為向後相容，且從此有歷史）。
- 不同且 `gate_mode≠off` → 409，訊息導引走版本 API。

---

## 7. Token 用量分流

### 7.1 資料流

```mermaid
graph TD
    subgraph 閘門驗證 / 優化迭代
        GR[Gate Run / Karpathy Loop] -->|X-Usage-Category + X-Eval-Run-Id| AC[AgentAPIClient → POST /agent/chat]
        GR -->|mutator.mutate 回傳 usage_metadata| MU[Mutator 記帳（新增，現況 100% 不落帳）]
    end
    AC --> AR[agent_router：header 存在且合法<br>→ request_type=eval_gate/prompt_optimize<br>+ run_id]
    AR --> RU[RecordUsageUseCase<br>fail-open，append-only]
    MU --> RU
    RU --> T[(token_usage_records<br>+ run_id 欄位)]
    T -->|audit 口徑：全計| OBS[observability /token-usage<br>零改動自然分組]
    T -->|billable 口徑：計入租戶配額<br>（定案 08-20）| Q[compute_quota → 配額/警報/auto-topup]
    T --> D[usage /daily /monthly<br>group-by 補 request_type]
```

### 7.2 實作點

| 項目 | 做法 |
|------|------|
| 新分類 | `UsageCategory` 加 `EVAL_GATE="eval_gate"`、`PROMPT_OPTIMIZE="prompt_optimize"`（皆 ≤ varchar(20)）；前端 `usage-categories.ts` 同步加 label（「閘門驗證」「Prompt 優化」） |
| 受測對話歸類 | `AgentAPIClient` 帶 `X-Usage-Category` + `X-Eval-Run-Id` header；`agent_router` 驗證（合法值白名單 + 登入角色）後傳入 `record_usage.execute(request_type=..., run_id=...)`。header 不合法 → 忽略、照舊記 `chat_web`（fail-open） |
| run_id 歸因 | `RecordUsageUseCase.execute` 加 optional `run_id` 參數（不佔用 `message_id`），寫入新欄位 |
| Mutator 記帳 | `run_use_cases._run_optimization` 在每次 mutate 後從 LangChain `usage_metadata` 取 token 數 → `record_usage(request_type=prompt_optimize, run_id=...)`，fail-open。背景任務用 independent session（沿 `process_document_use_case.py:415` 的 rebind 先例，但改用乾淨的 session factory 注入，不做屬性 rebind hack） |
| 計費口徑 | **【定案 08-20：租戶自付】** `sum_billable_tokens_in_cycle` **零改動**——新 category 與其他類別一樣預設計入配額（`included_categories=None` 全計的既有語意天然涵蓋）；未來若要對特定租戶改為平台吸收，用既有 `included_categories` 排除即可，零 schema 變更 |
| audit 口徑 | `sum_tokens_in_cycle` 不變（平台真實成本全計），儀表板可見 |
| `/by-bot`、`/token-usage` | group-by 已含 request_type，**零後端改動**，前端加 label 即可 |
| `/daily`、`/monthly` | repository `get_daily/monthly_usage_stats` 的 select+group_by 加 `request_type`，value objects 與 response 加欄位；前端折線圖支援按分類過濾 |
| 防濫用 | `StartGateRunUseCase` 前置：當日 `prompt_gate_runs` 計數 ≥ `gate_daily_limit` → 429；estimate 結果必須先呈現（前端流程強制），`est_cost` 寫入 run 列 |
| 索引 | 視需要補 `(tenant_id, request_type, created_at)` 複合索引（`sum_billable` 已在做 `IN (...)` 掃描，量大時受益）——列為 Phase B 選配 |

### 7.3 Phase B 開工前程式實況驗證（08-20，三路掃描）

計畫假設逐項對照後的**修正**（✅ 成立項不列）：

| # | 原計畫描述 | 程式實況 | 修正 |
|---|-----------|---------|------|
| 1 | mutator 記帳「沿 process_document rebind 先例」 | optimizer 背景任務**完全沒有 AsyncSession**（刻意只用 sync `RunHistoryClient`/`PromptDBClient`，`run_use_cases.py:36-38` 明文註記不碰 request-scoped session），rebind 無物可 rebind | 改用既有 `independent_session_scope()`（`session_middleware.py:37`）+ `async_session_factory()` 在背景任務內自建 RecordUsageUseCase，fail-open 包裝 |
| 2 | mutator 用 LangChain（暗示 Anthropic） | 是 `langchain_openai.ChatOpenAI`（gpt-4o-mini），`usage_metadata` 可取但未讀；retry 分支漏傳 api_key（順手修） | 記帳點 = `mutate()` 回傳 usage_metadata；provider 描述修正 |
| 3 | header 授權「JWT 具 eval 權限」 | `identity_source` 是 **body 自報值**（`agent_router.py:98`）不可作授權依據 | 授權以 `CurrentTenant.role ∈ {system_admin, tenant_admin}` 判定（`require_role` 先例）；header 不合法一律 fallback `chat_web`（fail-open） |
| 4 | 記帳 fail-open | `RecordUsageUseCase` 白名單是 **raise ValueError（fail-closed）**，且非 stream `/chat` 的記帳呼叫**沒包 try/except**（`agent_router.py:115`，失敗會炸使用者請求，違反工程約束） | Phase B 順手把該呼叫包 fail-open；新增 enum 值時前後端 label 同步為必要步驟（漏了會 500） |
| 5 | `/daily` `/monthly` group-by「確認是否自然支援」 | **不支援**：repo 只按日期/月分組、VO 無 request_type 欄位（對照 `/by-bot` 與 `/token-usage` 已支援=零改動 ✅） | 照原計畫改 repo+VO+response（工作量已列） |
| 6 | run_id 欄位 | `UsageRecord` entity / model / execute() 均無 run_id；`request_type` 是 **String(20) 硬上限**（現值 `contextual_retrieval` 已 20 頂滿） | 新三值 `eval_gate`(9)/`prompt_optimize`(15)/`playground`(10) 皆安全，**不需 ALTER 欄寬**；entity+model+execute 加 run_id/config_version_id |
| 7 | 計費零改動（定案 3） | `included_categories IS NULL` → 全計 ✅ 成立；但**已顯式設 list 的租戶**新分類不會計費（filter retroactive） | 行為正確（顯式名單=顯式意志），文件註記即可 |
| 8 | （新發現）schema drift | ORM 的 4 個 token_usage_records 索引中 3 個不在 `infra/schema.sql`（local DB 剛以 schema.sql 重建=實際缺索引） | Phase B migration 順手 `CREATE INDEX IF NOT EXISTS` 補齊 + 同步 schema.sql |
| 9 | （新發現）channel-parity 合規 | 規則要求 usage 記帳單一實作、禁通路特判分支 | header→category 解析做成 interfaces 層**共用 dependency**（usage-context resolver），非 router 內散落 if；通路覆蓋聲明：eval/playground 流量架構上只存在於 `/agent/chat`（api_client.py:82 唯一 caller），widget/LINE 無此流量、不受影響 |
| 10 | （新發現）eval 倍數 | validate 總呼叫數=題數×repeats；有 conversation_history 的題再 +N 次/題（`runner.py:306-318`） | estimate 與日限額計算（Phase C）需以此為準 |

**修 bug 的範圍聲明**（配合定案 3 調整）：現況的 bug 是「**分類錯誤**」（eval 流量被記成 `chat_web` 混入正式對話統計）與「**mutator 完全不落帳**」，分流上線後兩者修正。定案為租戶自付後，eval 用量**照常消耗配額、照常觸發警報/auto-topup**——這從此是正確行為而非 bug；租戶的保護靠 estimate 預檢、`gate_daily_limit`、`gate_budget_usd` 三道防線。既有被污染的 `chat_web` 紀錄不回溯改寫（append-only 紀律），必要時另出 backfill 腳本標注（不在 v1 scope）。

---

## 8. API 端點增修表

### 新增（新 router `prompt_version_router.py` + `prompt_gate_router.py`，DDD 四層各就位）

| Method | Path | 用途 | 權限 |
|--------|------|------|------|
| POST | `/api/v1/bots/{bot_id}/prompt-versions` | 建 draft（第 0 層靜態檢查；失敗 400 附明細） | tenant_admin+ 本租戶 |
| GET | `/api/v1/bots/{bot_id}/prompt-versions` | 版本列表（分頁、status filter） | 同上 |
| GET | `/api/v1/bots/{bot_id}/prompt-versions/{vid}` | 詳情 + 對 current 的 diff + gate run 摘要 | 同上 |
| POST | `/api/v1/bots/{bot_id}/prompt-versions/{vid}/validate` | 202 啟動 gate run（前置：三層開關、綁題集、日限額、預算） | 同上 |
| POST | `/api/v1/bots/{bot_id}/prompt-versions/{vid}/publish` | 發布；body `{force: bool}`（warn 模式失敗後強制發布用，block 模式 force 無效 409） | 同上 |
| POST | `/api/v1/bots/{bot_id}/prompt-versions/{vid}/reject` | 放棄 | 同上 |
| POST | `/api/v1/bots/{bot_id}/prompt-versions/rollback` | body `{target_version_id}` → 建新版直接 publish | 同上 |
| GET | `/api/v1/bots/{bot_id}/prompt-gate/estimate` | 驗證成本預檢（包 EstimateCostUseCase） | 同上 |
| GET | `/api/v1/prompt-gate/runs/{run_id}` | gate run 狀態/結果（前端 3s polling，沿 run-detail 模式） | 本租戶 |

### 修改

| 端點 | 變更 |
|------|------|
| `PUT /api/v1/bots/{id}` | base_prompt 攔截墊片（§6.5）；schema/response 加 6 個 gate_* 欄位 + 前置條件驗證 |
| `PATCH /api/v1/tenants/{id}/config` | 加 `prompt_gate_enabled` |
| `POST /api/v1/agent/chat` | 加 `prompt_override` + usage 標記 header（§6.1、§7.2；權限收緊） |
| `PUT /api/v1/prompt-optimizer/datasets/{id}` | 加 `bot_id`、`is_platform_base`（後者 system_admin only） |
| `POST /api/v1/prompt-optimizer/datasets/{id}/cases`（+新增 PATCH case） | case `enabled` 讀寫 |
| `POST /api/v1/prompt-optimizer/runs` | 迴圈影子執行；完成建 draft 版本；response 加 `version_id` |
| `POST /api/v1/prompt-optimizer/runs/{id}/rollback` | 改走版本 use case（§6.4） |
| `GET /api/v1/prompt-optimizer/runs*` 全組 | **補 tenant scoping**（事實校正 #9）；run_type 補齊 |
| `GET /api/v1/usage/daily`、`/monthly` | group-by 加 request_type（§7.2） |

---

## 9. UI 資訊架構

原則：URL 前綴保留 `/admin/prompt-optimizer`（避免路由大搬遷），側邊欄 label 改為「**Prompt 管理**」；hub 重組為完整入口。

```
側邊欄「AI 設定」group
└─ Prompt 管理  /admin/prompt-optimizer          【hub 重組：5 張卡】
   ├─ 版本與發布  /admin/prompt-optimizer/bots/:botId/versions   【新頁】
   │    版本時間線（status badge / 作者 / 來源 manual|optimizer|rollback）
   │    ├─ 版本詳情抽屜：diff vs current（復用 PromptDiff）、gate run 結果
   │    │   （失敗案例明細，復用 CaseResultsTable；硬斷言失敗紅色標記）
   │    └─ 操作：送驗（先顯示 estimate）/ 發布 / 強制發布(warn) / 放棄 / 回滾
   ├─ 啟動優化    /admin/prompt-optimizer/start          【保留；完成導向新版本】
   ├─ Run 歷史    /admin/prompt-optimizer/runs           【改造：統一 optimization|validation|gate 三類】
   │    └─ Run 詳情 /runs/:runId                          【改造：gate run 視圖；「套用」改「建立版本」】
   ├─ 題集管理    /admin/prompt-optimizer/datasets        【改造：+bot 綁定選擇器、case enabled、
   │                                                        平台通用集 badge/toggle(system_admin)】
   └─ 系統提示詞  /admin/prompts                          【併入 hub 卡片；頁面本身暫不動】

租戶端 Bot 設定頁  /bots/:id（bot-detail-form「LLM & Prompt」tab 擴充）
├─ base_prompt 編輯器【新增——現況 UI 完全無編輯入口】
│    儲存 = 建 draft 走狀態機；顯示目前線上版本號 + 最近 3 筆版本 + 「完整歷史」連結
└─ 發布閘門設定卡【新增】
     gate_mode(off/warn/block) / soft_threshold / repeats / auto_publish / daily_limit / budget
     未綁題集 → 鎖定 + 「須先設定問題集」導引；租戶 flag 關閉 → 整卡不渲染

Admin 租戶管理  /admin/tenants【改造：prompt_gate_enabled toggle】
Token 用量頁  /admin/token-usage、/token-usage【改造：+2 分類 label；daily 折線分類過濾】
```

頁面增減總計：**新增 1 頁**（版本時間線），**改造 6 頁**（hub、runs、run-detail、datasets/dataset-edit、bot-detail-form、admin-tenants），其餘保留。「驗收評估 validate」頁保留為獨立工具（手動驗任意 dataset×bot，與閘門互補）。

前端技術債順手處理（限於觸碰到的檔案）：`use-prompt-optimizer.ts` 的過時 `TestCase`/`EvalDataset` 型別對齊後端實際 shape（消除 `as never`/`as any`）；死碼 `run-progress.tsx` 不擴用。

---

## 10. 測試計畫

依 repo 紀律：先 `.feature` 後測試後實作；unit 一律 AsyncMock、禁真 DB；閘門判定邏輯完整單元覆蓋。

### 後端 unit（pytest-bdd，`tests/features/unit/prompt_gate/`）
| Feature | 覆蓋 |
|---------|------|
| `static_checks.feature` | 模板變數（合法/未知/巢狀）、長度邊界、injection 句式命中/未命中、空 prompt |
| `gate_verdict.feature` | **判定矩陣全覆蓋**：硬過×軟過、硬過×軟不過（門檻邊界 79.9/80.0）、硬不過×軟過、預算中止、P0 重跑 3 次 2 過 1 不過、unstable 標記、無軟斷言案例、severity 覆寫 |
| `version_state_machine.feature` | 全部合法轉移 + 全部非法轉移 409 + is_current 唯一性 + rollback 建版 |
| `gate_settings.feature` | 三層開關組合（tenant off / bot off/warn/block）、前置條件（未綁題集/全 disabled cases 不可啟用）、日限額 429 |
| `usage/eval_usage_split.feature` | 新 category 記帳、run_id 歸因、billable 預設排除 / 顯式計入、mutator 記帳 fail-open |
| `eval_dataset/optimizer_gate_handoff.feature` | 優化完成建 draft、baseline 未進步不建版、rollback 重導 |
| `agent/prompt_override.feature` | override 權限（widget/LINE 拒絕、無 eval header 拒絕）、組 prompt 取代邏輯 |

### 後端 integration（真 DB）
- 版本 API 全流程：create→validate→publish→rollback；tenant 隔離（跨租戶 404）。
- PUT /bots 墊片三情境（同值/off 改值/block 改值）。
- daily/monthly 分組回傳新分類；`/token-usage` 自然分組驗證。
- gate run 寫 `prompt_gate_runs` + usage 落帳 e2e（mock LLM 層）。

### 前端
- unit（vitest + vi.mock）：版本時間線元件、gate 設定表單（鎖定邏輯）、verdict banner。
- e2e（playwright-bdd，`e2e/features/admin/prompt-gate.feature`）：編輯→靜態檢查擋→修正→送驗（estimate 顯示）→失敗明細→修正重跑→通過→發布；warn 強制發布；未綁題集鎖定提示。補 `prompt-optimizer.feature` 基本 happy path（現況零 e2e）。

覆蓋率 ≥ 80%；Verdict Engine 與狀態機以 100% branch 為目標。

---

## 11. Phase 切分（階段二執行順序）

每個 phase：獨立可交付、附測試、migration+seed 齊備、更新 SPRINT_TODOLIST；建 1 個 GitHub Issue 統籌、每 phase 完成留 comment。

| Phase | 內容 | 產出即有的價值 | 依賴 |
|-------|------|--------------|------|
| **A 版本化底座** | `bot_prompt_versions` + backfill、version entity/repo/use cases（create/list/publish/reject/rollback + 靜態檢查）、版本 API、PUT 墊片 | 手動編輯從此有歷史、可回滾（閘門未上，全部 skipped 直發） | — |
| **B Token 分流** | UsageCategory+2、run_id 欄位、agent chat header、AgentAPIClient 標記、mutator 記帳、billable 預設排除、daily/monthly group-by、前端 label | **修正計費污染 bug**（eval 不再吃配額/觸發假金流）；與 A 平行可做 | — |
| **C 閘門引擎** | gate 設定欄位（bots/tenants）、`prompt_gate_runs`、eval_* 欄位、Verdict Engine、StartGateRun（含 estimate/日限額前置）、prompt_override eval 路徑、gate run API | 手動編輯走完整 draft→驗證→發布 | A、B(run_id) |
| **D Optimizer 整合＋加固** | 迴圈影子執行（不寫線上表）、產出→draft、rollback 收斂、平台集強制注入、run endpoints tenant scoping 補強、run_type 補齊 | 兩套系統合一；修「候選 prompt 污染線上」bug | A、C |
| **E 前端整合** | 版本時間線頁、bot Prompt tab（編輯器+閘門設定卡）、hub 重組、runs/dataset 頁改造、admin-tenants toggle、usage 圖表、e2e | 完整 UI 交付 | C、D |
| **F 平台通用集＋收尾** | 通用集 seed（Larry 圈題後）、文件更新（api-reference/configuration/architecture-journal）、`/sprint-sync` | 上線 ready | E |

註：A 與 B 無相互依賴，可並行或先 B（bug 修復價值高、範圍小）。

---

## 12. 待決清單：建議方案

> **定案狀態（08-20 Larry 回覆，已全數定案）**：#1=B 人工確認發布；#2、#4–#14 照建議；#3 改為租戶自付；#6 先定框架，題目圈選留 Phase F。**待決清單清空，可進入階段二。**

| # | 待決點 | 建議 | 理由 |
|---|--------|------|------|
| 1 | 通過後自動發布 vs 人工確認 | **【定案 08-20：B 人工確認】** bot 級 `gate_auto_publish` 預設 false；驗證通過停在 pending_publish，**發布前顯示完整驗證報告**（§4.5：逐題可展開回應 + DAG），人工按發布才上線 | 發布是外向不可逆動作；optimizer 產出尤其需要人看 diff；auto 留給 CI/自動化場景。與 warn/block 正交，組合語意清晰 |
| 2 | UsageCategory 拆兩類 vs 合一 | **拆 `eval_gate` / `prompt_optimize` 兩類** | 語意不同（治理成本 vs 改進投資），計費政策可能分別設定；append-only 帳本「合了拆不開、拆了隨時能加總」；兩名皆 ≤ varchar(20)；前端只是 +2 個 label |
| 3 | 計費預設：租戶配額 vs 平台吸收 | **【定案 08-20：租戶自付】** eval 兩類 token 一律計入租戶配額（billable 口徑預設全計，零邏輯改動）；平台 per-tenant flag 未開 = 該租戶根本產生不了這類用量，天然不會被計費 | Larry 決策：功能開給誰、誰就自己吸收用量；防護靠 estimate 預檢 + `gate_daily_limit` + `gate_budget_usd` 三道防線保護租戶配額；system tenant 自己的 gate/optimizer 用量記在 system tenant 名下（= 平台自付） |
| 4 | v1 版本化範圍 | **只 `base_prompt`，schema 帶 `target_field` 留擴充**（同 brief 建議） | `bot_prompt` 語意是附加指令、`worker_prompt` 在 `bot_workers` 另張表，各自接入成本高；`target_field` 是 optimizer 既有概念，沿用零成本，之後接入只是加 enum 值＋落地點 |
| 5 | system 帳號精確定義 | **`user.tenant_id == SYSTEM_TENANT_ID`（`00000000-...`，constants.py:3）即 system 帳號**；「預設開啟」= seed 把 SYSTEM tenant 的 `prompt_gate_enabled` 設 true。權限判定沿 `role == "system_admin"` | `is_system_admin()` helper 既有先例（`_admin_kb_check.py:23`）；tenant flag 統一控制、不需帳號級特例 |
| 6 | 平台通用集 v1 題目 | **附錄 A 提供 28 題候選清單**（`_security_base.yaml` 16 題全收 + `_prompt_injection_advanced.yaml` 精選 8 題 + 新增 4 題 RAG/拒答行為不變量），全部行為型/確定型斷言、hard severity、P0——請 Larry 圈選/增刪 | 素材現成（含 31 題孤兒檔正好活用）；行為型斷言把 judge 依賴降到零，重跑穩定 |
| 7 | 軟閘門 80% 與 N=3 | **採納**：`gate_soft_threshold=0.8`、`gate_repeats=3`（皆 bot 級可調，repeats 限 1–10）；重跑只施於 P0（P1/P2 跑 1 次） | 0.8 與現行 `VALIDATION_THRESHOLDS[P1]` 一致；N=3 對 P0 全過已有 (1-p³) 的抖動壓制，N=5（現 /validate 預設）成本 +67% 邊際效益低；P0-only 重跑讓成本 ≈ cases + 2×P0 |
| 8 | **（新增）gate run 執行機制**：asyncio.create_task（現況 optimizer 模式）vs arq worker | **v1 用 asyncio.create_task + `prompt_gate_runs` DB 持久化**；啟動時把孤兒 running 標 error。arq 化列後續加固（optimizer 一起搬） | brief 寫 arq 但現況不存在（事實校正 #2）；arq 需解決 worker 端 JWT/AgentAPIClient token 問題，改動面大；DB run 表已消除「process 重啟即失憶」的主要痛點；與 optimizer 機制一致、之後一起遷移 |
| 9 | **（新增）rollback 是否免重驗** | **免重驗直接 publish**（該快照曾過閘門；記 source=rollback 可稽核） | 回滾多發生在事故當下，速度優先；若題集後來變更導致舊 prompt 實質不合格，屬例外情境，可事後再驗 |
| 10 | **（v1.1）快照欄位白名單** | 照 §13.2 三分法：行為設定進快照；識別/憑證/外觀營運/治理觀測不進 | 憑證進快照 = 秘密擴散 + 回朔誤還原舊金鑰；治理設定（gate_*）進快照會出現「回朔把閘門自己關掉」的自指問題 |
| 11 | **（v1.1）非 prompt 設定變更是否過閘門** | **凡進快照的欄位變更一律走狀態機**；閘門依 gate_mode 統一適用，不按欄位細分 | 影子執行驗的是整包 effective config 的真實管線——temperature、檢索模式、top_k 改壞回答的能力不亞於 prompt；按欄位細分規則複雜且易漏 |
| 12 | **（v1.1）回朔合併語意** | **Overlay**：快照有的欄位套用，快照缺的（之後新增的欄位）保留現值，UI 標示「此欄位不在該版快照中」 | 硬回朔缺欄位會把新功能設定重設成 default（隱性破壞）；overlay 保守且可稽核 |
| 13 | **（v1.1）效果驗證分層納入範圍** | 層次 1（版本數據歸因 + 版本成效卡）納入 v1（Phase A/E）；層次 2（真實流量回放 pairwise 對比）列 Phase G；層次 3（線上 A/B 分流）backlog 註記 | 層次 1 改動小、直接支撐「每版本所有數據」需求；層次 2 依賴影子執行落地；層次 3 POC 流量撐不起統計顯著性 |
| 14 | **（v1.2）Playground 用量分類** | **【定案 08-20：同意】** 新增第三個分類 `playground`（≤ varchar(20)），不併入 `eval_gate` | 語意不同（人工試玩 vs 閘門驗證），租戶帳單上分開才看得懂「錢花在哪」；帳本拆了隨時能加總、合了拆不開（同待決 2 的理由） |

---

## 13. v1.1 增補：Bot 設定整包版控（取代 §3.1 prompt-only 設計）

> 需求（Larry 08-20）：「追蹤不同版本的所有數據以及設置，每個版本的設置可以做 git 版控，最後可以直接選擇回朔。」
> 設計轉向：版本的單位從「一段 prompt」升級為「**一份 bot 行為設定快照（config as commit）**」。prompt 仍是快照中的一個欄位；狀態機、閘門、發布流程全部沿用，只是受版控的內容變寬。

### 13.1 快照欄位白名單（三分法）

Bot 實體 45 欄逐一歸類（依 `domain/bot/entity.py` 現況）：

| 類別 | 欄位 | 進快照 |
|------|------|--------|
| **Prompt 類** | `base_prompt`、`bot_prompt`、`memory_extraction_prompt`、`query_rewrite_extra_hint`、`hyde_extra_hint` | ✅ |
| **LLM 參數** | `llm_provider`、`llm_model`、`llm_params`（temperature / max_tokens / history_limit / frequency_penalty / reasoning_effort / rag_top_k / rag_score_threshold）、`router_model`、`summary_model` | ✅ |
| **RAG 檢索** | `rag_retrieval_modes`、`query_rewrite_enabled/model`、`hyde_enabled/model`、`rerank_enabled/model/top_n`、`tool_configs`（per-tool 覆蓋）、`knowledge_base_ids` | ✅（KB 只版控**綁定清單**，KB 內容本身不在版控範圍——快照說明需標注此限制） |
| **Agent 行為** | `enabled_tools`、`max_tool_calls`、`memory_enabled`、`memory_extraction_threshold`、`mcp_bindings`（**剝除 `env_values`**，只存 registry_id + enabled_tools） | ✅ |
| 識別/中繼 | id、short_code、tenant_id、name、description、created_at、updated_at | ❌ |
| **憑證（紅線）** | `line_channel_secret`、`line_channel_access_token`、`mcp_bindings.env_values` | ❌ 絕不入快照（秘密擴散 + 回朔誤還原舊金鑰） |
| 外觀/營運 | `is_active`、`fab_icon_url`、`widget_*` 全組、`busy_reply_message`、`customer_service_url`、`show_sources`、`line_show_sources` | ❌ 直接更新、不產生版本 |
| 治理/觀測 | `gate_*` 六欄、`eval_provider/model/depth` | ❌（gate 設定入快照會出現「回朔把閘門關掉」自指問題；eval 設定影響觀測不影響回答） |
| Deprecated | `intent_routes`、`mcp_servers` | ❌ |

### 13.2 Schema 修訂（取代 §3.1）

```sql
CREATE TABLE bot_config_versions (
    id              VARCHAR(36) PRIMARY KEY,
    tenant_id       VARCHAR(36) NOT NULL,
    bot_id          VARCHAR(36) NOT NULL REFERENCES bots(id) ON DELETE CASCADE,
    version_no      INTEGER     NOT NULL,               -- 每 bot 遞增
    config_snapshot JSONB       NOT NULL,               -- §13.1 白名單欄位整包
    snapshot_schema INTEGER     NOT NULL DEFAULT 1,     -- 快照結構版本（欄位演進用）
    changed_fields  JSONB       NOT NULL,               -- 相對上一版變更欄位清單（列表顯示/diff 加速）
    status          VARCHAR(20) NOT NULL DEFAULT 'draft',
    is_current      BOOLEAN     NOT NULL DEFAULT FALSE,
    source          VARCHAR(20) NOT NULL DEFAULT 'manual',
    source_run_id   VARCHAR(36),
    gate_run_id     VARCHAR(36),
    gate_verdict    VARCHAR(20),
    author_user_id  VARCHAR(36),
    published_at    TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (bot_id, version_no)
);
-- 索引同 §3.1（bot/tenant/partial unique is_current），移除 target_field 維度
```

- 其餘設計不變：append-only、`bots` 表保留為 denormalized 讀取快照（publish 時同交易套用白名單欄位 + 翻 is_current + invalidate cache）、backfill migration 改為對每個 bot 快照現行整包設定為 version 1。
- 待決點 4（target_field 擴充）由本設計吸收——`bot_prompt` 等欄位天然在快照內，不再需要 target_field 機制；`bot_workers`（supervisor/worker）仍不在 v1 範圍。
- 狀態機（§4.1）、靜態檢查（§4.2，僅施於 prompt 類欄位）、判定引擎（§4.4）不變。

### 13.3 影子執行升級：`prompt_override` → `config_override`

§6.1 的 override 從單一 prompt 字串升級為快照 overlay：gate run 以「現行 bot 實體 ⊕ draft 快照」組出 effective bot 跑真實管線（RAG 檢索模式、top_k、rerank、工具集全部生效）——**驗的是整包設定的真實行為**，這正是待決點 11 建議「設定變更也過閘門」的技術基礎。權限收緊與通路限制同 §6.1 不變。優化器路徑只 override prompt 欄位（快照其餘取現值），機制同一套。

### 13.4 `PUT /api/v1/bots/{id}` 墊片修訂（取代 §6.5）

按 §13.1 白名單把 payload 二分：

1. **非版控欄位**（外觀/營運/憑證/治理）→ 直接更新，不產生版本（現行為不變）。
2. **版控欄位**有變更 → 建 draft 走狀態機：`gate_mode=off` 透明代發布（向後相容）；`≠off` 回 409 導引版本 API。
3. 同請求同時含兩類 → 非版控部分即時生效，版控部分依 2 處理（response 明確標示兩者狀態）。

### 13.5 回朔（Rollback）語意

- 選任一歷史 published 版本 → 建新版本（source=rollback、快照複製）→ 免重驗直接 publish（待決點 9）。
- **Overlay 合併**：套用快照有的欄位；快照缺的欄位（該版之後才新增的功能）保留現值，版本詳情 UI 標示「不在該版快照」；憑證/外觀永不被回朔動到。
- `snapshot_schema` 欄位保留結構演進空間（v1 恆為 1，讀取端向後相容）。

### 13.6 每版本數據歸因（「追蹤不同版本的所有數據」的落地）

- 生成路徑打標：`messages`（或 `agent_execution_traces.metadata`）、`rag_evaluations`、`token_usage_records` 各加 `config_version_id`（生成當下的 is_current 版本）。寫入點在 send_message 管線一處，fail-open。
- **版本成效卡**（版本詳情頁）：服役區間（published_at → 下一版 published_at）、訊息數、L2 faithfulness/relevancy 平均、feedback 正評率、平均延遲/first_token、每則成本、guard 攔截數——全部按 version_id 聚合，與前後版本並排。
- 版本列表升級為「版本 × 設定變更（changed_fields）× 服役數據摘要」總表：一眼看出「v7 上線後 L2 掉了 0.1」→ 點開 → 一鍵回朔 v6。
- 誠實限制標注於 UI：前後對照含時間混淆因子（流量組成變化），小流量下為方向性參考，非嚴格因果。

### 13.7 對 Phase 切分的影響

| Phase | 變更 |
|-------|------|
| A 版本化底座 | 表改 `bot_config_versions`、快照白名單序列化/overlay 邏輯、PUT 墊片二分——工作量 +30% 左右 |
| B Token 分流 | `token_usage_records` 的 `config_version_id` 併入此 phase 的欄位 migration |
| C 閘門引擎 | override 直接做成 config overlay（不先做 prompt-only 再改） |
| E 前端 | 版本頁含欄位級 diff（prompt 用文字 diff、其他欄位用 field diff）+ 版本成效卡 |
| **G（新增，選配）** | 真實流量回放 pairwise 對比（§14 層次 2）：抽最近 N 則真實問題 → 新舊版影子執行 → LLM judge 換位 pairwise → win/lose/tie 報告 | 

---

## 14. 發布後效果驗證（v1.1 增補：閘門證「沒變爛」，這裡證「有變好」）

三層次，由淺入深（詳細討論見 08-20 對話紀錄）：

| 層次 | 機制 | 時機 | 納入 |
|------|------|------|------|
| **1. 版本歸因 + 前後指標對照** | §13.6：既有線上數據（`rag_evaluations` L1/L2/L3、`feedback`、traces 延遲、usage 成本、guard_logs）按 version_id 切開比較 | 發布後持續 | **v1**（Phase A/E） |
| **2. 真實流量回放 pairwise 對比** | 抽真實問題 → 新舊兩版 config 影子執行 → LLM judge pairwise（A-B/B-A 換位防 position bias）→ 勝負報告；同時補齊 §6.3 缺的 run A vs B 比較視圖 | 發布**前**的決策點 | Phase G（選配） |
| **3. 線上 canary / A/B 分流** | 部分流量走新版 + 統計檢定；版本表已天然支援多 published 共存，只缺 serving 層選版邏輯 | 發布後 | backlog（POC 流量不足） |

與 observability 升級計畫的閉環：層次 2 的「真實問題抽樣」與該計畫 2-P4「爛 trace 一鍵入題集」共用素材管道；層次 1 的版本成效卡是該計畫「run 比較視圖」的線上版對應物。

---

## 15. v1.2 增補：儲存前對照測試 Playground（side-by-side 前後版本聊天室）

> 需求（Larry 08-20）：改設置/改 prompt 儲存前，可**選擇性**開一個對照聊天視窗：使用者輸入一句話，並排看到「現行版 vs 草稿版」的回應與各自的執行軌跡 DAG（React Flow trace 圖）。
> 與閘門的關係：**不衝突，互補**——Playground 是「小樣本、人工判斷、答『感覺好不好』」；閘門是「全題集、斷言判定、答『有沒有踩到底線』」。兩者共用同一套影子執行（config_override），Playground 本質上就是 §14 層次 2（pairwise 對比）的手動即時版。

### 15.1 UI 設計（掛在 bot 編輯頁 / 版本詳情的 draft 上）

```
┌─ 對照測試：v12（線上） vs 草稿 ── [設定差異: temperature 0.3→0.7, base_prompt] ─┐
│  ┌──── 線上 v12 ────────┐  ┌──── 草稿 ──────────┐                              │
│  │ 回應氣泡              │  │ 回應氣泡            │   每則回應卡片：              │
│  │ ▸ 執行軌跡 DAG        │  │ ▸ 執行軌跡 DAG      │   延遲 / tokens / 成本        │
│  │ ▸ 檢索命中 chunks     │  │ ▸ 檢索命中 chunks   │   （展開比對）                │
│  └──────────────────────┘  └────────────────────┘                              │
│  [輸入一句話，同時發給兩版...........................................] [送出]     │
│  底部動作列： [放棄草稿]  [送驗（閘門）]  [直接發布*]   *依 gate_mode 決定可用性   │
└────────────────────────────────────────────────────────────────────────────────┘
```

- 一次輸入 → 同時打兩版（並行兩個影子請求）；**多輪各自延續自己的對話脈絡**（兩版回答不同，後續分岔是預期行為，UI 標明）。
- 兩欄各自可展開執行軌跡 DAG（復用 `live-trace-graph.tsx` 即時 trace 元件）與檢索 chunks——這是「為什麼答案不一樣」的解釋層。
- 頂部常駐設定 diff 摘要（changed_fields），底部動作列把 Playground 與狀態機動作串成一條流。

### 15.2 執行機制（全部復用，只加隔離規則）

| 面向 | 做法 |
|------|------|
| 兩版執行 | 皆走 `config_override` 影子執行（線上版也用 override 跑，兩邊條件對稱：同樣不寫對話庫） |
| 隔離（test mode flag） | 不寫 `conversations`/`messages`、**不觸發 memory extraction**、不跑線上 L1/L2/L3 eval、不算入對話統計；guard 照跑（真實管線的一部分） |
| Trace | 照常收集、隨 response 串流回前端（餵 DAG），**不持久化**（或持久化並標 `is_test`——傾向不存，省表膨脹） |
| Usage 記帳 | 照記（租戶自付，定案 3），新分類 `playground`（待決點 14）；歸因 version_id 兩邊各記各的 |
| 防濫用 | 沿用既有 rate limit；不另設日限額（單次成本 ≈ 2 則對話，estimate 免跑，UI 顯示累計花費即可） |

### 15.3 與閘門/狀態機的關係（衝突分析結論）

1. **狀態機零影響**：Playground 作用於 draft，不改變 status；測完要上線仍依 gate_mode 走原流程（block 模式照樣要過閘門才能發布）。
2. **開支各自獨立可選（定案 08-20）**：Playground 對任何 gate_mode 的租戶都是**每次儲存時隨用隨選**——gate_mode=on 也可以這次不用；入口按鈕旁常駐備註「**此功能將消耗 token（約 2 則對話/次，計入租戶用量）**」。兩者都不用 = 儲存零 token 開支（純版本快照）。
3. **語意互補不重疊**：Playground 答不了「30 題資安不變量還過不過」（人不會每次都試注入攻擊），閘門答不了「語氣符不符合品牌」（斷言測不出來）。設計上讓兩者出現在同一條動作列，鼓勵「先玩幾句 → 再送驗 → 發布」。
4. 唯一的真交集：兩者都吃 config_override 影子執行（Phase C 產物）——是共用地基，不是衝突。

### 15.4 Phase 歸屬

- 後端（test mode 隔離旗標 + playground usage 分類）：併入 **Phase C**（影子執行本來就要做，隔離規則是增量）。
- 前端（對照聊天室 + 雙 DAG）：併入 **Phase E**（復用 Studio chat 與 live-trace 元件）。
- §14 層次 2（自動回放 pairwise）仍列 Phase G——Playground 先上，等於層次 2 的手動前身，共用全部管道。

---

## 附錄 A：平台通用集 v1 候選題目（28 題，待 Larry 圈選）

> 全部 P0、硬 severity、行為型/確定型斷言（零 LLM judge 依賴）。來源標注供對照。

**一、來自 `_security_base.yaml`（16 題全收）**
direct_override ×3、role_play ×3、data_exfil ×3、indirect_injection ×3、encoding_bypass ×2、functional_abuse ×2 —— 斷言以 `no_system_prompt_leak` / `no_role_switch` / `not_contains`(升 hard) / `refused_gracefully` 為主。

**二、精選自 `_prompt_injection_advanced.yaml`（8 題）**
| 類別 | 題數 | 理由 |
|------|------|------|
| crescendo（多輪漸進誘導） | 2 | 唯一覆蓋 conversation_history 攻擊面的類別 |
| tool_manipulation（誘導濫用工具） | 2 | 直接對應 `tool_not_called` 硬斷言 |
| payload_splitting（拆分載荷） | 2 | 靜態檢查攔不到、必須動態驗 |
| delimiter_confusion + language_switch | 各 1 | 覆蓋格式混淆與跨語攻擊 |

**三、新增 RAG/行為不變量（4 題，需新寫）**
| 題目意圖 | 斷言 |
|---------|------|
| 知識庫內必答題（例：營業時間類通用問法） | `tool_was_called: rag_query` + `response_not_empty` |
| 知識庫外問題不臆造 | `refused_gracefully` + `no_hallucination_markers` |
| 索取他人個資 | `no_pii_leak` + `refused_gracefully` |
| 閒聊不觸發工具濫用 | `tool_call_count: {max: 0}` 或 `tool_not_called` |

> 註：第三組的「必答題」依賴 bot 知識庫內容，通用集只能放「行為模式」級題目；具體領域題屬 bot 自訂集。

---

## 附錄 B：本規劃引用的關鍵程式位置速查

| 主題 | 位置 |
|------|------|
| 迴圈中途寫線上 prompt | `prompt_optimizer/runner.py:193` → `db_client.py:49-65`；closure `run_use_cases.py:225-232` |
| 無白名單 setattr rollback | `run_use_cases.py:604-670`（L639/L650） |
| N 次重跑聚合 | `prompt_optimizer/validation_evaluator.py:27-97`（索引對齊問題 L57） |
| case 級門檻 | `prompt_optimizer/evaluator.py:85 VALIDATION_THRESHOLDS` |
| eval token 誤記 chat_web | `eval_use_cases.py:510-536` → `api_client.py:66-104` → `agent_router.py:115-121` |
| mutator 不落帳 | `prompt_optimizer/mutator.py:36-79` |
| 計費口徑 | `application/quota/compute_tenant_quota_use_case.py:88-91`、`usage_repository.py:343-352` |
| bot 級設定 12 落點鏈 | 見探索紀錄；樣板 `eval_depth`（`domain/bot/entity.py:102` 起） |
| prompt 讀取端（發布生效點） | `send_message_use_case.py:355-364` |
| system 帳號 | `domain/shared/constants.py:3`、`_admin_kb_check.py:23-28` |
