# 防護階段三層設定（Guard Stages，Issue #75）

> 防護階段像 worker 一樣可勾選：**系統層管底線與預設、方案層給不同預設、租戶與 bot 只能在底線之上加嚴**；
> 系統管理員可鎖定特定租戶；不論誰改都寫稽核，系統管理員對某租戶的變更該租戶看得到（操作者標「平台」）。
> 沿用 #68 abuse_settings 的三層 resolve 模式，共用機制抽在 `domain/settings/layered.py` 與
> `application/settings/layered_provider.py`。

## 1. 階段清單

| stage | 對應程式 | 成本 | 說明 |
|-------|----------|------|------|
| `regex_input` | `PromptGuardService.check_input` | 0 | 正則 / 關鍵字輸入防護（0 ms 第一關） |
| `classifier_attack` | 意圖分類器 `is_attack` | 1 次小模型 | fast / deep 沿用分流那次呼叫；**kb 模式不帶 worker 只做攻擊判定**（`classify_sanitize(workers=[], attack_only=True)`） |
| `output_guard` | `PromptGuardService.check_output` | 0 | 輸出關鍵字防護（含 `GuardedAgentService` 咽喉點） |
| `abuse_scoring` | P7 `evaluate` / `record` | 0（Redis） | 異常使用者分級控管的計分與查級 |
| `local_classifier` | — | — | 預留（地端小模型），目前解析為 no-op |

平台預設（Q7，Larry 09-07 定案）：

- **底線（required）**：`regex_input` + `output_guard` + `abuse_scoring` — 任何層都關不掉
- **平台預設啟用**：底線 + `classifier_attack`
- 內建方案：`standard`（沿用平台預設）、`exhibition`（展覽用：關 `classifier_attack`，省一次小模型）

## 2. 三層 + bot 的解析規則

```
有效階段 = required ∪ 方案預設（無方案覆寫時 = 平台預設）∪ 租戶加嚴 ∪ bot 加嚴
```

| 層 | scope_kind / 位置 | 可設的鍵 | 規則 |
|----|-------------------|----------|------|
| 平台 | `guard_settings(platform, "*")` | `stages`、`required_stages` | 底線與預設；只有 system_admin 可改 |
| 方案 | `guard_settings(profile, <name>)` | `stages` | 給租戶一組預設集合（可少於平台預設，但底線由聯集保證） |
| 租戶 | `guard_settings(tenant, <tenant_id>)` | `stages`、`profile`、`locked` | **只能加不能減**；`locked=true` 時忽略租戶與 bot 覆寫；只有 system_admin 可改 |
| bot | `bots.guard_stages`（JSON，NULL = 繼承） | 清單 | 儲存時驗證必須是租戶有效集合的**超集**；租戶被鎖定時不得自設（422） |

- 未知階段名 → `422 Unknown guard stage`。
- `required_stages` 只准在 platform；`locked` / `profile` 只准在 tenant。
- 解析結果 `EffectiveGuard(stages, required, locked, source_map, profile)`；`source_map` 標每個階段來自
  `required` / `platform` / `profile` / `tenant` / `bot`（DB 失效時為 `fallback`）。

## 3. 快取與 fail-safe

- `CachedGuardProvider`：每租戶快取 60 秒；後台儲存後立即清快取（租戶層只清該租戶，平台 / 方案層清全部）。
- **DB 失效 → 全部階段開啟（fail-safe，防護寧多勿少）**，與異常控管的 fail-open 相反。
- bot 存了未知階段（舊資料）→ 忽略 bot 層，不因此降低防護。

## 4. 管線（三通路同一份）

web / widget（`SendMessageUseCase` execute + stream）與 LINE（`HandleWebhookUseCase`）每回合取一次
`EffectiveGuard`，之後每段防護都經由 `application/security/guard_pipeline.py::GuardPipeline` 決定跑不跑：

| 階段 | 開 | 關 |
|------|----|----|
| `regex_input` | `check_input`（LINE 仍與分類並行） | 不呼叫；咽喉點也不補跑 |
| `classifier_attack` | fast / deep：採用分流那次的 `is_attack`；kb：多一次不帶 worker 的攻擊判定 | 忽略 `is_attack`；kb 不呼叫小模型 |
| `output_guard` | `check_output`（web 在 use case、LINE 在咽喉點） | 不呼叫 |
| `abuse_scoring` | `evaluate` + `record` | 不查級、不計分 |

- 有效階段清單放進 agent metadata `_guard_stages`，`GuardedAgentService` 咽喉點依此跳過關閉的階段
  （未帶清單的舊接線 / 新通路仍全部跑，「預設生效」契約不變）。
- trace 多一個 `guard_stages` 節點（metadata：`stages` / `sources` / `required` / `locked`）。
- `guard_provider` 未注入（舊接線 / 單元測試）時退回全部階段開啟 = #75 之前的行為。

## 5. 稽核

- 三層任何寫入 → `audit_logs`：`entity_type=guard_settings`、`entity_id=<scope_kind>:<scope_id>`、
  `action=update`、`before/after` = 覆寫 dict、`tenant_id` = 目標租戶（tenant scope）或 NULL。
- system_admin 對 **tenant scope** 的寫入 `source="platform"`；租戶端變更紀錄
  `GET /bots/{bot_id}/audit-logs`（#71）會併入 `entity_id=tenant:<tenant_id>` 的這些列，
  `actor_label="平台"`、`entity_type="guard_settings"`。
- bot 自己的 `guard_stages` 走既有 bot 稽核與設定快照（`guard_stages` 已加入快照白名單）。

## 6. API

| Method | Path | Auth | 說明 |
|--------|------|------|------|
| GET | `/api/v1/admin/guard/settings` | system_admin | 總覽：平台覆寫、方案、預設有效值、階段清單、底線預設、各層允許鍵 |
| PUT | `/api/v1/admin/guard/settings/platform` | system_admin | `{"overrides": {"stages": [...], "required_stages": [...]}}` |
| PUT | `/api/v1/admin/guard/settings/profiles/{name}` | system_admin | `{"overrides": {"stages": [...]}}` |
| GET | `/api/v1/admin/guard/settings/tenants/{tenant_id}` | system_admin / 本租戶 tenant_admin | 該租戶的方案、覆寫、鎖定、有效值、`editable` |
| PUT | `/api/v1/admin/guard/settings/tenants/{tenant_id}` | system_admin | `{"profile": "...", "overrides": {"stages": [...]}, "locked": true\|false}` |
| GET | `/api/v1/guard/effective?bot_id=` | tenant_admin / system_admin | 某 bot 的有效防護（跨租戶 → 404） |
| POST / PUT | `/api/v1/bots` / `/api/v1/bots/{bot_id}` | 既有 | 多 `guard_stages: string[] \| null` 欄位（超集規則；鎖定時 422） |

`/api/v1/guard/effective` 回應：

```json
{
  "tenant_id": "t1",
  "bot_id": "bot-1",
  "stages": ["regex_input", "classifier_attack", "output_guard", "abuse_scoring"],
  "required": ["regex_input", "output_guard", "abuse_scoring"],
  "locked": false,
  "source_map": {
    "regex_input": "required",
    "classifier_attack": "platform",
    "output_guard": "required",
    "abuse_scoring": "required"
  },
  "profile": "standard",
  "bot_stages": null,
  "available_stages": ["regex_input", "classifier_attack", "output_guard", "abuse_scoring", "local_classifier"]
}
```

## 7. Migration

`apps/backend/migrations/add_guard_settings.sql`（冪等）：`guard_settings` 表（與 `abuse_settings` 同構）+
`bots.guard_stages JSON NULL`。依 `.claude/rules/migration-workflow.md` 兩環境（local-docker / company-poc-vm）各走五步。
