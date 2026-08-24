<!-- 由 Workflow wf_ffa3e29c-ab9 產生，純靜態讀碼、未執行任何程式、未修改任何原始碼 -->

> **審查方法**：15 個 finder 代理分區 × 維度靜態讀碼（Fable 5）→ 每個 finding 交 2 名獨立反駁者定點查證（Opus 5，prompted to REFUTE，2 票反駁即剔除、1 票即降級）→ 資安類再過第 3 個「攻擊者可利用性」視角調整嚴重度 → 合成去重分級。50 個代理、315 萬 token、975 次工具呼叫。
>
> **可信度提醒**：123 個原始 findings 中僅 1 個被反駁剔除、0 個降級。存活率 99% 偏高，兩種解讀都可能——finder 本身精準，或反駁者對抗性不足。**採信任何一項前請自行覆核 `file:line` 證據**，尤其是 MEDIUM/LOW 段。CRITICAL/HIGH 段的資安項目另有可利用性代理獨立查證過利用鏈，可信度較高。

# 全專案深度 Code Review 報告（2026-08-20）

## 統計摘要

| 項目 | 數值 |
|------|------|
| Finder 數 | 15 |
| 原始 findings | 123 |
| 對抗性驗證剔除 | 1 |
| 降級（DOWNGRADED） | 0 |
| 通過驗證的 findings | 122 |
| 語意去重合併 | 18 項（14 組重複） |
| **最終 findings** | **104** |
| 最終嚴重度分布 | CRITICAL 9 / HIGH 20 / MEDIUM 53 / LOW 22 |
| 審查檔案（reviewed_union） | 198 項（含測試 / feature / 設定檔），其中對應生產程式碼 **168** 檔 |
| 全量生產檔（backend .py + frontend .ts/.tsx，排除 `__init__.py`、`*.test.*`、`*.d.ts`） | **788** |
| 未被任何 finder 讀過 | **620**（覆蓋率 21.3%） |

> 說明：本次為「Issue #54 發布閘門 / 版本治理」為主軸的深度 review，15 個 finder 依功能面分區。覆蓋率偏低是刻意的分區聚焦結果，未覆蓋清單見文末——其中 `interfaces/api/`（30 檔 router，含 `auth_router.py`）與 `application/knowledge/`（29 檔）是風險最高的未審區塊，建議列為下一輪 review 的第一優先。
>
> **本次審查中反覆出現的系統性根因**（跨多個 finding，建議以此為修復單位而非逐項修）：
> 1. **「知道 id 就能存取」的授權缺口** — 大量 use case 以純 id 查詢、不比對 tenant_id（C2/C4~C9、L11、M36）
> 2. **通路對等 drift** — 管線步驟只實作在單一通路（H7/H8/H9/H11、M15~M22）；違反 `.claude/rules/channel-parity.md`
> 3. **test_mode 六面隔離不完整** — guard log / trace 例外分支 / intent classify 未納入（H6、M8~M10、M14）
> 4. **request-scoped session 被背景任務借用** — `get_tracked_session` + 長 await（H13/H14、M29/M30）
> 5. **前端快取失效鏈斷裂** — mutation 只 invalidate 自己那條 key（H18、M40/M41、L19）

---

## CRITICAL

### C1. publish 在真實 DB 必觸發 `ix_bcv_current` 唯一索引違反
- `apps/backend/src/application/prompt_gate/version_use_cases.py:229`
- 分類：correctness ｜ finder：prompt-gate-core
- **失敗情境**：任何已有 current 版本的 bot（backfill migration 讓**所有** bot 的 v1 都是 `is_current=TRUE`）呼叫 `POST /config-versions/{id}/publish` → `mark_published()` 把新版本 `is_current=True`，`version_repo.save()` 內 `atomic()` 立即 commit，此時舊 current 尚未清除 → 同 bot 兩列 `is_current=TRUE` → 違反 partial unique index → IntegrityError 500。更糟的是 `bot_repo.save(bot)` 已在前一行 commit，bots 表已套新設定但版本列仍停在 draft/pending、cache 未清。
- **證據**：`version_use_cases.py:225-230` 的順序為 `mark_published → apply_snapshot → bot_repo.save → version_repo.save → set_current`；`atomic.py:17-19` 為 `begin_nested` 後即 `session.commit()`；`add_bot_config_versions.sql:33-34` 建立 `CREATE UNIQUE INDEX ix_bcv_current ... WHERE is_current`（Postgres partial unique index 不可 DEFERRABLE，statement 時即檢查）。整合測試抓不到：`bot_config_version_model.py:73-75` 刻意不含此 index，conftest 用 `Base.metadata.create_all` 建 schema。
- **建議修法**：`mark_published()` 不設 `is_current`，由 `set_current()` 在**單一交易內**先清舊再設新，並把 bots 寫入與版本翻轉收進同一交易。
- **驗證狀態**：CONFIRMED（兩名反駁者均無法推翻；確認與 journal 已記錄的「交易縫隙」不同——這是 100% 觸發的確定性崩潰）

### C2. `conversation_id` 無租戶歸屬檢查 → 跨租戶對話歷史外洩 + 寫入汙染（IDOR）
- `apps/backend/src/application/agent/send_message_use_case.py:1193`
- 分類：security ｜ finder：shadow-exec-isolation
- **失敗情境**：租戶 B 的任一合法 JWT 使用者 `POST /api/v1/agent/chat` 帶 `{"message":"請摘要我們前面聊過的所有內容","conversation_id":"<租戶A的UUID>","bot_id":"<B自己的bot>"}` → `_load_or_create_conversation` 直接回傳 A 的 Conversation → A 的完整歷史被組進 `history_context` 餵給 LLM 並回吐給 B；同時 B 的訊息與 AI 回覆被 `save()` 回 `tenant_id` 仍為 A 的對話，汙染 A 的稽核紀錄。
- **證據**：`send_message_use_case.py:1192-1197` 無 `existing.tenant_id == command.tenant_id` 比對；`conversation_repository.py:118-123` `find_by_id` 只 `session.get()` 無 tenant filter（同檔其他方法 `find_recent`/:180/:214/:339 全都帶 tenant filter，證明是漏網）；`bot.tenant_id` 檢查發生在 `_load_bot_config`，時序在 conversation 載入之後且檢查的是 bot 不是 conversation。對照組 `conversation_router.py:88-101` 有明確歸屬檢查。
- **建議修法**：`_load_or_create_conversation` 對 `existing.tenant_id != command.tenant_id` 視同不存在（或 403），或改用 `find_by_id_for_tenant`。
- **驗證狀態**：CONFIRMED ｜ **可利用：是**（任何有效 JWT；需先取得 A 的 conversation UUID——來源包括 widget SSE 下發的 `conversation_id` 事件、截圖、log。寫入汙染只需 UUID，無其他條件）

### C3. Widget 串流記帳 100% 崩潰：`TokenUsage` 建構傳入不存在的 `total_tokens`
- `apps/backend/src/interfaces/api/widget_router.py:218`
- 分類：correctness ｜ finder：usage-attribution + agent-pipeline（同時發現）
- **失敗情境**：任何 widget 訪客完成一輪對話 → `if usage_data:` 進入 → `TokenUsage(..., total_tokens=usage_data.get("total_tokens",0), ...)` 直接 `TypeError`（Token-Gov.6 後 `total_tokens` 改為 `@property`）→ 例外發生在 try 之外、且 `done` 事件已送出 → 使用者無感、伺服器只留 generator exception → **widget 通路 token 用量 100% 漏記**，quota 不扣、計費全逃逸且無告警。
- **證據**：`domain/rag/value_objects.py:48-72` frozen dataclass 欄位只有 model/input/output/estimated_cost/cache_read/cache_creation；反駁者實測 `TypeError: TokenUsage.__init__() got an unexpected keyword argument 'total_tokens'`。`infrastructure/langgraph/usage.py:83-96` `build_usage_event` 必帶 `total_tokens`，故每輪必觸發。對照 `agent_router.py:347` 正確使用 `extract_usage_from_accumulated()`。commit `fbeeec6` 改 VO 時漏改此呼叫點，且無任何 widget usage 測試。
- **建議修法**：改用 `extract_usage_from_accumulated(usage_data)`（順帶補回 cache token 欄位），並補 widget stream 記帳 regression test。
- **驗證狀態**：CONFIRMED（含實際執行驗證）

### C4. `GET /datasets/{id}` 與 `/export` 無租戶歸屬檢查 → 跨租戶讀取任意題集
- `apps/backend/src/interfaces/api/eval_dataset_router.py:263`（`/export` 於 :410）
- 分類：security ｜ finder：eval-dataset + security-tenant-isolation（同時發現）
- **失敗情境**：任一租戶持合法 JWT 呼叫 `GET /api/v1/prompt-optimizer/datasets/{他人dataset_id}` → 回傳完整題集：`tenant_id`、`bot_id`、全部 test_cases 的 question / assertions / conversation_history。
- **證據**：handler 簽章為 `_: CurrentTenant = Depends(get_current_tenant)`（tenant 被綁到 `_` 丟棄）；`GetEvalDatasetUseCase.execute(dataset_id)` 無 tenant 參數；`eval_dataset_repository.py:70-78` WHERE 只有 `id == dataset_id`。router 無 router-level dependencies、main.py 無 tenant middleware、全 repo 無 RLS。對照 `list_datasets`（:210）有 tenant scoping。
- **建議修法**：handler 取得 dataset 後比對 `ds.tenant_id == tenant.tenant_id or tenant.role == 'system_admin' or ds.is_platform_base`，不符回 404。
- **驗證狀態**：CONFIRMED ｜ **可利用：是**（平台通用集 100% 可達：跑一次自家 gate run，`GateRunResponse.dataset_ids` 會回傳平台集 UUID；針對特定他租戶則需先知其 uuid4，故實務性略低於字面）

### C5. `PUT` / `DELETE /datasets/{id}` 無租戶歸屬檢查 → 跨租戶竄改與不可復原刪除
- `apps/backend/src/interfaces/api/eval_dataset_router.py:287`（DELETE 於 :319）
- 分類：security ｜ finder：eval-dataset ×2 + security-tenant-isolation（三項合併）
- **失敗情境**：租戶 A 對平台通用集發 `PUT {"default_assertions": []}`（body **不帶** `is_platform_base` 即完全繞過唯一的 system_admin 守衛）→ 所有租戶的 gate run 失去平台級安全斷言；或 `DELETE` 直接刪除整份題集（連 test_cases 級聯，無 soft-delete、無備份）。
- **證據**：`router:282-286` 唯一的授權檢查是 `if body.is_platform_base is not None and tenant.role != 'system_admin'`——守的是旗標不是那一列，且條件為 `is not None`；`UpdateEvalDatasetCommand` 根本沒有 `tenant_id` 欄位；`repo.save` 用 `session.merge(model)` 依 id 寫回；`repo.delete` WHERE 只有 id。後果放大：`gate_run_use_cases.py:150-152` 把 `ds.default_assertions` 併進每個 GateCase。
- **建議修法**：Update/Delete use case 加 `tenant_id` 參數並比對；`is_platform_base=true` 的內容修改與刪除一律限 system_admin。
- **驗證狀態**：CONFIRMED ｜ **可利用：是**（任一低權限租戶使用者，單一 HTTP 請求，無 role 檢查、無稽核、無還原路徑）

### C6. Test case CRUD（POST/PATCH/DELETE）無租戶/角色驗證 → 可靜默關閉全平台發布閘門
- `apps/backend/src/interfaces/api/eval_dataset_router.py:525`（POST :485、DELETE :533）
- 分類：security ｜ finder：eval-dataset + security-tenant-isolation（同時發現）
- **失敗情境**：任一租戶使用者取得平台通用集 id → 逐一 `PATCH /datasets/{platform_ds}/cases/{case_pk} {"enabled": false}` 停用全部平台安全題 → `gate_run_use_cases.py:130` 的 `enabled_cases` 過濾對平台集同樣生效 → 所有租戶的閘門驗證失去平台級安全把關，**題集仍在、UI 看起來正常**。`DELETE` 更直接：router:546 丟棄路徑上的 `dataset_id`，`DeleteTestCaseUseCase` 以純 PK 刪除任意租戶題目，不存在也回 204。
- **證據**：三個 case 端點皆 `_: CurrentTenant`（未使用）；`UpdateTestCaseUseCase`（`manage_test_cases_use_case.py:53-67`）只驗 dataset 存在與 case 屬於該 dataset；`is_platform_base` 的 system_admin 守衛只存在於 `update_dataset`，完全不涵蓋 case 端點。完整利用鏈已逐環驗證（gate estimate → dataset_ids → GET dataset → case PK → PATCH）。
- **建議修法**：三個 case 端點先載 dataset 比對 tenant 歸屬；平台集的 case 寫入限 system_admin；`DeleteTestCaseUseCase` 必須驗 case 屬於指定 dataset。
- **驗證狀態**：CONFIRMED ｜ **可利用：是**（門檻＝任一租戶的任一登入使用者；亦可反向注入必失敗的硬斷言造成全平台發布 DoS）

### C7. `/eval`、`/validate`、`POST /runs` 不驗 dataset 租戶歸屬 → 題集內容經執行結果外洩
- `apps/backend/src/application/eval_dataset/eval_use_cases.py:45`（另 :471、`run_use_cases.py:92`）
- 分類：security ｜ finder：eval-dataset
- **失敗情境**：租戶 A 以他人 `dataset_id` 呼叫 `POST /eval` 或 `/validate` → 回應的 `case_results` 含每題 question 全文；`POST /runs` 更把整個題集 snapshot（含 conversation_history、assertions）寫進 A 可見的 run iterations。
- **證據**：三個 use case 的 command 都有 `tenant_id` 欄位卻只用於 metadata / usage 記帳，從未與 `dataset.tenant_id` 比對；router（`eval_dataset_router.py:579-585`、`643-651`；`prompt_optimizer_run_router.py:144-154`）也無檢查。對照組：run 的讀取端點有 `_scope(tenant)` + `_check_run_tenant`，唯獨建立/執行路徑沒有。
- **建議修法**：三個 use case 在 `find_by_id` 後加 `if dataset.tenant_id != command.tenant_id and not (平台集 or admin): raise EntityNotFoundError`。
- **驗證狀態**：CONFIRMED ｜ **可利用：是**（需先取得 dataset_id；以 system_admin 身分 `GET /datasets` 可列出全部租戶題集）

### C8. `GET /api/v1/bots/{bot_id}` 缺租戶歸屬檢查 → 跨租戶讀取完整 Bot 設定（含明文 LINE 憑證）
- `apps/backend/src/interfaces/api/bot_router.py:545`
- 分類：security ｜ finder：security-injection
- **失敗情境**：租戶 A 使用者呼叫 `GET /api/v1/bots/{租戶B的bot_id}` → 回傳整包設定，其中 `line_channel_secret` / `line_channel_access_token` **以明文回傳** → 攻擊者可直接冒充受害者的 LINE 官方帳號對其全部好友推播；`bot_prompt` / `base_prompt` / `kb_ids` / gate 設定亦全數外洩。
- **證據**：`get_bot` 只 `Depends(get_current_tenant)`；`GetBotUseCase.execute(bot_id)` 無 tenant 參數；`bot_repository.py:406-408` `select(BotModel).where(BotModel.id == bot_id)` 無 tenant where。`bot_router.py:396-397` 原值回傳憑證，對照同函式 `mcp_bindings` 於 :345-347 有 `dict.fromkeys(..., "***")` 遮罩。無 router dependencies、無 middleware、無 RLS。
- **建議修法**：加 `if bot.tenant_id != tenant.tenant_id and tenant.role != "system_admin": 404`（須保留 system_admin 跨租戶檢視），且 LINE 憑證不應在 GET 回應明文回傳。
- **驗證狀態**：CONFIRMED ｜ **可利用：是**（bot_id 出現在 Studio URL、embed/config payload；以 system_admin 身分 `GET /api/v1/admin/bots` 可列出全部）

### C9. `PUT` / `DELETE /api/v1/bots/{bot_id}` 缺租戶歸屬檢查 → 跨租戶竄改 / 刪除他人 Bot
- `apps/backend/src/interfaces/api/bot_router.py:582`（DELETE :634）
- 分類：security ｜ finder：security-injection
- **失敗情境**：租戶 A 以自己的 token `PUT /api/v1/bots/{租戶B的bot_id}` → 可覆寫 B 的 `bot_prompt` / `base_prompt`（注入任意指令，直接服務於 B 的真實客戶）、改寫 `line_channel_secret` / `line_channel_access_token` 把通道指向自己，或 `DELETE` 造成永久服務中斷。
- **證據**：`_build_update_command(bot_id, body)` 從不放入 `tenant.tenant_id`（`UpdateBotCommand` 無此欄位）；`update_bot_use_case.py:341-344` 只有 `find_by_id` + None 檢查即 `_apply_updates` → `save`；`delete_bot_use_case.py:17-27` 同型。唯一 tenant-aware 的 `validate_bot_enabled_tools` 只驗工具白名單且僅在 `body.enabled_tools is not None` 時執行。`_DIRECT_FIELDS`（:140）包含兩個 LINE 憑證欄位。
- **建議修法**：`UpdateBotCommand` / `DeleteBotUseCase` 加入 tenant_id 並在取得 bot 後比對，不符 raise `EntityNotFoundError`。
- **驗證狀態**：CONFIRMED ｜ **可利用：是**（與 C8 同前置條件；跨租戶寫入 + 摧毀，實務影響高於 C8）

---

## HIGH

### H1. gate 啟用時 rollback 必被 `GateBlockedError` 擋下，違反「回朔免重驗直接發布」定案
- `apps/backend/src/application/prompt_gate/version_use_cases.py:316` ｜ correctness ｜ prompt-gate-core
- **失敗情境**：`tenant.prompt_gate_enabled=True` 且 `bot.gate_mode ∈ {warn, block}` → `POST /config-versions/rollback` 建出 `status=draft, source=rollback` 的新版本後呼叫 `publish.execute(verdict=VERDICT_SKIPPED, force=False)` → `_gate_active` 為 True → `_resolve_gate_verdict` 走 STATUS_DRAFT 分支一律 raise → 409。**閘門開啟的環境（正是最需要緊急回朔的環境）rollback 功能完全不可用**。
- **證據**：`version_use_cases.py:220-223` 在 caller 傳入的 verdict 之前無條件覆寫；`:190-199` draft 的唯一逃生口是 `warn + force + gate_verdict==fail`；`version.source == SOURCE_ROLLBACK` 從未被 gate 邏輯讀取。與自身 docstring「免重驗直接發布（定案 9）」及 `entity.py:35` 註解直接矛盾。測試不覆蓋（`test_version_state_machine_steps.py:125` 建構 publish_uc 時不傳 tenant_repo）。
- **建議修法**：`_resolve_gate_verdict` 對 `source == SOURCE_ROLLBACK` 短路回傳 `VERDICT_SKIPPED`，或提供內部 `bypass_gate` 參數。
- **驗證狀態**：CONFIRMED

### H2. gate / replay / optimizer 影子自呼叫 URL 寫死 `localhost:8001`，生產容器 listen 8000
- `apps/backend/src/application/prompt_gate/gate_run_use_cases.py:90`（另 `replay_use_cases.py:89`、`eval_dataset/run_use_cases.py:71`、`eval_use_cases.py:27/451`）｜ correctness ｜ prompt-gate-background + session-lifecycle（同時發現）
- **失敗情境**：Cloud Run 上觸發 `POST /validate` 或 `/replay-compare` → AgentAPIClient 打 `http://localhost:8001` → connection refused → `_run_single_case` 吞例外回空 answer → `_assert_case` 對每題產生 `api_error` hard fail → **閘門在部署環境 100% 判 fail**，`gate_mode=block` 時該 bot 任何版本永遠無法發布。只有本機 `make dev-backend`（`${PORT:-8001}`）能動。
- **證據**：`container.py` 全檔 grep `api_base_url` 零命中（兩個 provider 均未注入）；`config.py` 無任何對應設定；`Dockerfile` `ENV PORT=8000` + `CMD uvicorn --port $PORT`；`deploy-backend.yml:88` `--port=8000`。唯一用 8001 的是 `Makefile:21`——本機 dev 值外洩成生產預設。
- **建議修法**：Settings 增加 `self_api_base_url`（預設 `http://localhost:${PORT}`），container 明確注入到四個 use case，並在 Cloud Run 驗證一次 gate run 打通。
- **驗證狀態**：CONFIRMED（部署面證據齊全）

### H3. 背景任務持 15 分鐘 access token 且無 refresh_token，長 run 中途 401 全數誤判 api_error
- `apps/backend/src/application/prompt_gate/gate_run_use_cases.py:354` ｜ correctness ｜ prompt-gate-background
- **失敗情境**：使用者登入 10 分鐘後才觸發 gate run，或 run 本身跑超過 token 剩餘壽命（cases × repeats × 每題數十秒很容易超過 15 分鐘）→ 每題 chat 回 401 → `_refresh_access_token` 因 `refresh_token=""` 直接回 False → `raise_for_status` → 空 answer → 之後每題 hard fail `api_error` → run 判 fail、版本退回 draft，**前半段已燒掉的 token 成本白費**。
- **證據**：`config.py:26` `jwt_access_token_expire_minutes: int = 15`；建構 AgentAPIClient 未傳 refresh_token（`api_client.py:33` 預設 `""`，:56-59 直接回 False）；對照組 `prompt_optimizer_run_router.py` 的 `StartRunRequest` 有 `refresh_token` 欄位且有傳。
- **建議修法**：validate/replay 端點比照 `StartRunRequest` 接收 refresh_token 傳入，或改用服務內部憑證執行影子呼叫。
- **驗證狀態**：CONFIRMED（此問題目前被 H2 完全遮蔽——連不上就談不到 401，須一併修）

### H4. validate / replay 端點無角色限制，但影子執行授權要求 admin → 一般 user 觸發必全滅並燒光日限額
- `apps/backend/src/interfaces/api/bot_config_version_router.py:372` ｜ security ｜ prompt-gate-background + usage-attribution（同時發現）
- **失敗情境**：`role="user"`（註冊預設值）的租戶成員呼叫 `POST /config-versions/{id}/validate` → 前置檢查全過、run 建立、版本進 validating、日限額 count 掉一次 → 背景 chat 帶 `X-Usage-Category: eval_gate` 但 `resolve_usage_context` 因 role ∉ `{system_admin, tenant_admin}` fallback 為 `chat_web` → `_require_shadow_authorized` 回 403 → 每題空 answer hard fail → run 必定 fail、版本退回 draft。重複呼叫即可燒光 `gate_daily_limit`，阻斷 admin 當日正常驗證。
- **證據**：`bot_config_version_router.py` 全檔無 `require_role`（`deps.py:67` 的 helper 未被使用）；`usage_context.py:34` `_ALLOWED_ROLES`；`agent_router.py:88-103` 的 403；`prompt_gate_run_repository.py:86-98` `count_today` 以 `created_at` 計數不分成敗。
- **建議修法**：**整個 config-version router 補 `require_role("system_admin","tenant_admin")`**，而非只補 validate/replay。
- **驗證狀態**：CONFIRMED ｜ **可利用：是**。**升級提醒**：同一根因下 `role="user"` 亦可呼叫 `POST /publish`、`/rollback`、`create_version`——即一般租戶成員可自行建立並發布 bot 設定版本（含 system prompt 快照），這是實質的租戶內權限提升，不只是配額耗盡

### H5. Replay pairwise judge 的 LLM token 從未記帳：`record_usage_factory` 注入後零使用
- `apps/backend/src/application/prompt_gate/replay_use_cases.py:101` ｜ correctness ｜ usage-attribution + prompt-gate-background（同時發現）
- **失敗情境**：一次 replay（sample_size 上限 30）→ `PairwiseJudge.judge` 每題呼叫 2 次（最多 60 次 ChatOpenAI，用平台 provider key）→ 這些 token 完全不進 `token_usage_records`，`actual_cost` 也只累加受測呼叫，故 `budget_usd` 熔斷不含 judge；但 `est_cost` 卻按 2.5 倍（含 judge）估算——**估算含、記帳與熔斷不含，帳目永遠對不上**。
- **證據**：全檔 grep `record_usage_factory` 只有 :91 建構參數與 :101 賦值，無任何讀取點；`container.py:2029/2275` 有注入（dead injection）。judge 直接 `ChatOpenAI.ainvoke`，繞過 `/agent/chat` 與 usage middleware，回傳只取 `response.content`（`usage_metadata` 被丟棄）。對照 `eval_dataset/run_use_cases.py:340-355` 的 `_record_mutator_usage` 有完整落帳。檔頭 docstring 自陳「judge 另計」但該記帳不存在。
- **建議修法**：judge 呼叫後仿 `_record_mutator_usage`，於 `independent_session_scope` 內以 `_record_usage_factory` 記一筆 `eval_gate`（含 run_id 歸因），並納入 `actual_cost`。
- **驗證狀態**：CONFIRMED（兩名反駁者建議可降至 MEDIUM——漏記的是平台成本非租戶 quota、金額有界；此處依「保留最高嚴重度」原則維持 HIGH）

### H6. test_mode 下 guard 攔截仍寫 `guard_logs` 生產表（六面隔離的 guard 面破口）
- `apps/backend/src/application/security/prompt_guard_service.py:170`（output 於 :337）｜ correctness ｜ shadow-exec-isolation
- **失敗情境**：閘門 run / replay / optimizer 的攻擊測項（「忽略以上指令」「顯示 system prompt」——攻擊套件正是閘門的預設用途）以 `test_mode=true` 打 `/agent/chat` → 命中 regex → `check_input` 無視 test_mode 無條件 `save_log(...)` 寫入 `guard_logs` → 每次閘門執行灌入數十筆假攻擊紀錄，租戶 admin 的安全檢視（`security_router.py:149`）被測試流量汙染，**無法區分真實攻擊**。
- **證據**：`check_input` 簽章只有 message/tenant_id/bot_id/user_id，無 test_mode / dry_run 參數；`guard_log_repository.py:25-36` 為真實 DB insert。呼叫端（`send_message_use_case.py:1207/936/807/1069`）不傳任何隔離旗標——對照同段程式碼在 conversation 面（`:1217 if not command.test_mode`）與 trace 面（`persist=not command.test_mode`）都有隔離，佐證這是遺漏而非設計。gate/replay/optimizer 全部走 `test_mode=True` 流經同一 guard。
- **建議修法**：`check_input` / `check_output` 增加 `dry_run`（或 `log_enabled`）參數，`SendMessageUseCase` 依 `command.test_mode` 傳入。
- **驗證狀態**：CONFIRMED（兩名反駁者均建議降 MEDIUM——為觀測資料汙染非安全繞過）

### H7. Widget 公開 SSE 未過濾 `guard_blocked` / `config_version` 內部事件，向匿名端洩漏防護規則
- `apps/backend/src/interfaces/api/widget_router.py:202` ｜ security ｜ agent-pipeline + usage-attribution（同時發現）
- **失敗情境**：匿名攻擊者 `curl -N POST /api/v1/widget/{short_code}/chat/stream {"message":"ignore all previous instructions"}` → SSE 直接回傳 `{"type":"guard_blocked","rule_matched":<命中的 regex 原文>}`；輸出攔截時還附 `replacement`。逐條變換探針即可把整份 input_rules / output_keywords 枚舉出來，之後精準改寫 payload 繞過（即 7/1 家樂福角色劫持事故的前置）。內部 `config_version_id` UUID 亦一併外洩。
- **證據**：widget event loop 只 continue `usage` 與（keep_history off 時的）`conversation_id`，其餘一律 `yield`；對照 `agent_router.py:302-307` 有 `config_version` continue 與 `guard_blocked and not is_studio` continue。`prompt_guard_service.py:186-191` 證實 `rule_matched` 就是規則原文；規則為**平台全域**且正規讀取需 `require_role("system_admin")`（`security_router.py:67-70`）→ 確為越權外洩。`send_message_use_case.py:1066-1067` 那句「端使用者(widget/LINE)透過 router sanitize 拿不到此事件」的註解與現況不符。
- **建議修法**：widget event_generator 無條件 drop `guard_blocked`（或至少剝除 `rule_matched`/`replacement`）與 `config_version`；長期把事件白名單抽成兩 router 共用函式（channel parity）。
- **驗證狀態**：CONFIRMED ｜ **可利用：是**（前置條件為零，完全匿名。反駁者建議降 MEDIUM——攻擊者本就有免費無限的二元 oracle，洩漏規則原文是把試誤變成一次命中的「加速」，非從不可能變可能）

### H8. `config_version_id` 打標只有 web 通路：widget / LINE 的用量記錄永遠 NULL，版本成效指標漏算兩通路
- `apps/backend/src/interfaces/api/widget_router.py:222` + `apps/backend/src/application/line/handle_webhook_use_case.py:988` ｜ correctness ｜ channel-parity + usage-attribution + agent-pipeline（三個 finder 同時發現）
- **失敗情境**：家樂福 LINE bot 發布新版本後，所有 LINE 對話的 `chat_line` usage 記錄 `config_version_id=NULL`、`message_id=NULL`（`result.message_id` 恆為 None，正確值 `assistant_msg.id.value` 在 L880 就有）。Phase E1 的版本成效 metrics API 以 `token_usage_records.config_version_id` 為唯一錨點聚合 → **對 LINE-only 的 POC bot，版本數據歸因整段為空**，發布閘門的線上成效判讀失真，且 UI 無任何「資料只含單一通路」的標示。widget 側同樣缺 `message_id` 與 `config_version_id`（且目前被 C3 的 TypeError 完全遮蔽——連 usage record 本身都不存在）。
- **證據**：打標點只存在於 `agent_router.py:161`（非串流）與 `:357`（串流）；`widget_router.py:222-227` 與 `handle_webhook_use_case.py:986-994` 都只傳 tenant_id/request_type/usage/bot_id；`version_metrics_repository.py:27-42` 的 `_usage_scope` / `_message_ids_subq` 完全以 `config_version_id == version_id` 為錨。`container.py:2489-2517` 的 `HandleWebhookUseCase` 未注入任何 config_version repository。`AgentResponse.message_id` 全 src 只有 `send_message_use_case.py:836` 一處賦值。違反 `channel-parity.md` 紅線 1（usage 記帳屬管線步驟，只能有一份）。
- **建議修法**：把 `_resolve_current_version_id` 的打標移進共用層（順手還債優先於再堆一層）；LINE 端改傳 `message_id=assistant_msg.id.value`；widget 端比照 agent_router 捕獲 `message_id` / `config_version` 事件（並 continue 不下發，與 H7 一起改）。
- **驗證狀態**：CONFIRMED

### H9. LINE 意圖分類呼叫漏傳 `tenant_id` / `bot_id` → intent_classify token 記到 `tenant_id=""` 的孤兒帳
- `apps/backend/src/application/line/handle_webhook_use_case.py:690` ｜ correctness ｜ channel-parity
- **失敗情境**：任一配置了 workers 的 LINE bot，每輪對話一次分類器 LLM 呼叫，其 token 以 `tenant_id=""`、`bot_id=None` 寫入 UsageRecord → 租戶 quota 不扣這筆（計費繞過）、usage 報表出現無主記錄；web 同一功能正常計入。
- **證據**：`classify_sanitize` 簽章有 `tenant_id: str = ""`、`bot_id: str | None = None` 預設值，LINE 呼叫只傳 user_message/router_context/workers/router_model；`intent_classifier.py:298-304` 用該 tenant_id 呼叫 `record_usage.execute`；`record_usage_use_case.py:81-96` 對空字串無驗證即建立並 save，`token_usage_records.tenant_id` 只是 `String(36)` 無 FK → 靜默落孤兒帳。對照 `send_message_use_case.py:588-595` web 端有傳。
- **建議修法**：`classify_sanitize` 呼叫補上 `tenant_id=bot.tenant_id, bot_id=bot.id.value`。
- **驗證狀態**：CONFIRMED（一名反駁者建議降 MEDIUM——分類器單次 token 量小）

### H10. `line_show_sources=True` 時 dict 型 sources（DM 快速道）觸發 AttributeError → 使用者收不到任何回覆
- `apps/backend/src/application/line/handle_webhook_use_case.py:876` ｜ correctness ｜ channel-parity
- **失敗情境**：bot 開啟 `line_show_sources`、direct_retrieval 快速道命中且 DM 工具回傳 sources（`result.sources = list(rr.sources) + list(dm_sources)`，dm_sources 是 dict）。當文字檢索命中 <3 筆使 dict 進入前 3 名 → `s.score` 對 dict 拋 AttributeError → 例外發生在 L939 的 try/finally **之前** → reply 未送出、對話與 trace 未持久化、endpoint 回 500 → LINE redelivery 重複觸發。
- **證據**：`L873-877` 迴圈無 dict 分支；同檔 `L861-867`（retrieved_chunks）與 `L893-901`（image_sources）都已明確處理 dict / Source 兩型（`L890-892` 註解自述），**唯獨參考來源區塊漏改**；`L503` 快速道明確把 dict 型 dm_sources 塞進 `result.sources`。
- **建議修法**：參考來源迴圈比照 image_sources 做 `isinstance(s, dict)` 分支。
- **驗證狀態**：CONFIRMED（觸發需合取條件：`line_show_sources=True` + 快速道 + DM 命中 + 文字檢索 <3 筆，反駁者建議降 MEDIUM）

### H11. 分類器語意攻擊閘門（`is_attack`）只有 LINE 有 → web/widget 同一攻擊句直接進生成模型
- `apps/backend/src/application/agent/send_message_use_case.py:588` ｜ security ｜ channel-parity
- **失敗情境**：繞過 regex guard 的語意型攻擊（同義改寫、拆字、外語、多輪鋪陳）：LINE 路徑由 `classify_sanitize` 判 ATTACK → `block_by_classifier` 短路；web/widget 路徑用 `classify_workers`（內部雖轉呼 `classify_sanitize` 但 **`is_attack` 被丟棄**）→ 攻擊句照常進主模型。與 7/1 家樂福角色劫持事件同構的「防護只在單一通路」drift（當年 web 有 LINE 沒有，這次反向）。
- **證據**：`prompt_guard_service.py:190-193` 明確註記「LLM 語意判斷（原 llm_input_guard）已於 2026-08-17 移除：語意層的注入/角色切換判定併入意圖分類器」——**語意防護在兩通路都被拆掉，替代品只接在 LINE**；全 src grep `is_attack|block_by_classifier|classify_sanitize` 只有 `handle_webhook_use_case.py:690/697/776` 三個命中點。web/widget 現在只剩 0ms regex 一關。
- **建議修法**：web `_resolve_worker_config` 改用 `classify_sanitize`（或抽共用 service），`is_attack` 時走與 LINE 相同的 `block_by_classifier` 短路。
- **驗證狀態**：CONFIRMED ｜ **可利用：是**（`POST /api/v1/widget/{short_code}/chat/stream` 是完全匿名的 public endpoint，直接呼叫同一個 `SendMessageUseCase`；兩名反駁者與可利用性評估者皆建議**上修**，因為這是移除語意防護後未接上替代閘門造成的實質退化，暴露面在匿名網際網路）

### H12. `POST /datasets/import` 接受 `body.tenant_id` → 任意租戶可冒名寫入他租戶命名空間
- `apps/backend/src/interfaces/api/eval_dataset_router.py:362` ｜ security ｜ eval-dataset
- **失敗情境**：租戶 A 送 `{"yaml_content": ..., "tenant_id": "<租戶B>"}` → dataset 以 `tenant_id=B` 建立，出現在 B 的題集列表 → B 誤以為是自己的題集拿去跑 eval，燒 B 的 token，且惡意 YAML 的問題文本可對 B 的 bot 做 prompt injection 式測試。
- **證據**：`tenant_id = body.tenant_id or tenant.tenant_id`（:362）之前無任何 role 判斷；`ImportDatasetRequest.tenant_id` 對所有已認證使用者開放。對照同檔 :282 對 `is_platform_base` 有明確 system_admin 守衛、`create_dataset`（:237）強制用 `tenant.tenant_id`，可證此為 import 端點特有的鬆綁。
- **建議修法**：非 system_admin 一律忽略 `body.tenant_id`，強制使用 `tenant.tenant_id`。
- **驗證狀態**：CONFIRMED ｜ **可利用：是**（需知道受害租戶 tenant_id 字串——可從 C4 的 GET dataset 回應或匯出檔 metadata 取得）

### H13. `/validate` 在 request 內同步跑長時 LLM 迴圈 → session idle-in-transaction 120 秒被 DB 砍線，驗證歷史必然寫入失敗
- `apps/backend/src/application/eval_dataset/eval_use_cases.py:587` ｜ correctness ｜ eval-dataset
- **失敗情境**：10 題 × 5 repeats、每次 chat 約 4 秒 → 迴圈約 200 秒。`find_by_id`（:471）已在 request session 上 autobegin 開啟交易，之後 session 閒置 → 120 秒後 PostgreSQL 依 `idle_in_transaction_session_timeout` 終止該連線 → 迴圈結束後 `save_iteration` 用同一個死 session → 寫入失敗被 except 吞成 warning → **任何超過 120 秒的驗證跑完後歷史紀錄永遠不會落庫**。repeats 上限 100 更會讓 request 跑數小時，撞上 proxy/Cloud Run timeout 連回應都拿不到。
- **證據**：`container.py:2258-2262` 該 use case 的 `optimization_run_repository` 綁 `db_session`（per-request singleton）；`engine.py:23-25` `server_settings={'idle_in_transaction_session_timeout':'120000'}` 且註解自陳「長操作已用 close-session/refresh pattern 主動處理」——而此路徑正好沒做；優化 run 走背景任務 + `independent_session_scope`，唯獨 `/validate` 留在 request 內（兩套重複程式的行為分歧）。
- **建議修法**：驗證改走背景任務（同 `StartRunUseCase` 模式），或至少 history 寫入包 `independent_session_scope` 取新 session。
- **驗證狀態**：CONFIRMED（校準：「必然」僅在牆鐘時間超過 120s 時成立，短題集可能成功）

### H14. 背景 log cleanup loop 借用 tracked session 且永不關閉 → 首次 idle-txn 被 PG 砍斷後清理永久失效
- `apps/backend/src/main.py:62` ｜ correctness ｜ session-lifecycle
- **失敗情境**：lifespan 以 `create_task` 起 `_log_cleanup_loop`。第一次迭代 `container.log_retention_policy_repository()` 經 `db_session=Factory(get_tracked_session)` 建 session 並存進該 task context 的 ContextVar（無 `independent_session_scope`、無人 close）→ 裸 SELECT autobegin 開交易後 `continue`（政策未到期的常態路徑）→ 120s 後連線被 PG 砍 → 下一小時迭代拿到同一顆死 session → OperationalError → 之後每小時 PendingRollbackError，被 except 吞成 warning → **log retention 清理從此永不執行直到重啟**，該 session 佔用的 pool 連線也不歸還。
- **證據**：同檔 gate 孤兒清理（:117-121）有正確包 `async with independent_session_scope():`，此 loop 完全沒有；`session_middleware.py:26-33` 只會重用 ContextVar 中既有 session，`SessionCleanupMiddleware` 只在 `scope['type']=='http'` 生效，背景 task 走不到；`pool_pre_ping` / `pool_recycle` 只在 checkout 時作用，救不了已持有的連線。疊加 H16（pricing refresh 汙染 lifespan context）後，此 loop **連第一次都不會成功**。
- **建議修法**：loop 每次迭代包 `async with independent_session_scope():`（含 `repo.get` 與 `uc.execute`）。
- **驗證狀態**：CONFIRMED（兩名反駁者均建議降 MEDIUM——背景維運功能，不影響線上對話）

### H15. CLI `run` 的 target level 對映與 `_TARGET_MAP` 相反，所有內建範例 dataset 直接崩潰
- `apps/backend/prompt_optimizer/__main__.py:94` ｜ correctness ｜ optimizer-package
- **失敗情境**：執行模組 docstring 的文件用法 `python -m prompt_optimizer run --dataset datasets/ecommerce_example.yaml --db-url ...` → `target_level = "system" if target_field in ("base_prompt",) else "bot"` 把 `base_prompt` 映到 `('system','base_prompt')`，該 key 不在 `_TARGET_MAP` → `ValueError('Unknown target')` 開跑即崩潰。
- **證據**：`db_client.py:14-22` `_TARGET_MAP` 只有 `('system','system_prompt')`、`('bot','bot_prompt')`、`('bot','base_prompt')`——**與 CLI 的判斷完全顛倒**。實測 4 個內建 dataset：ecommerce/education/saas 皆 `target_prompt: base_prompt`，joyinkitchen 是 `react_prompt`（→ `('bot','react_prompt')` 也不在 map）→ **4 個全炸**。API 路徑 `run_use_cases.py:275-277` 用 `bot_id` 判斷是正確的，只有 CLI 錯。
- **建議修法**：改為 `target_level = "system" if target_field == "system_prompt" else "bot"`，或依 `bot_id` 判斷與 `run_use_cases` 一致。
- **驗證狀態**：CONFIRMED（一名反駁者建議降 MEDIUM——影響面僅限 CLI 開發工具，且為開跑即失敗的顯性錯誤）

### H16. API 優化路徑建 CLIDataset 時未把 `default_assertions` 併入各 case → 資料集層級斷言（含安全斷言）全程不被評估
- `apps/backend/src/application/eval_dataset/run_use_cases.py:243` ｜ correctness ｜ optimizer-package
- **失敗情境**：租戶在 dataset 設 `default_assertions`（例如 `no_role_switch` / `no_system_prompt_leak` 安全預設）→ 從前端啟動優化 run → 建 TestCase 時只帶 `tc.get("assertions")`，defaults 只掛在 `CLIDataset.default_assertions` 而 `Evaluator._evaluate_case` 從不讀取 → **優化分數完全忽略預設安全斷言**，mutator 可接受一個違反安全預設的 prompt 並產出 draft 版本，且與 gate run（有合併）判定不一致。
- **證據**：`evaluator.py:201` `for assertion in tc.assertions`，全檔無 `default_assertions` 參照；DB 內的 per-case 斷言確定不含 defaults（`eval_dataset_router.py:383-390` 匯入時明寫「excluding defaults which are already in default_assertions」並過濾）；對照組 `dataset.py:_parse_cases:197`、`db_client.read_dataset:216`、`gate_run_use_cases.py:151` 都有合併，唯獨 `run_use_cases` 與 `eval_use_cases`（見 M31）漏了。
- **建議修法**：建 TestCase 時以 `list(defaults) + case assertions` 合併（比照 `DatasetLoader._parse_cases`）。
- **驗證狀態**：CONFIRMED（一名反駁者建議降 MEDIUM——目前平台基準集 seed 的 `default_assertions` 為 `[]`，安全題全在 per-case，故現況只在租戶自建/匯入題集時發作）

### H17. 選「（預設）」rewrite/HyDE 模型會存入單一空白字元 → rewrite/HyDE 每次靜默失敗退回 raw query
- `apps/frontend/src/features/bot/components/bot-detail-form.tsx:357`（HyDE 於 :412）｜ correctness ｜ frontend-existing
- **失敗情境**：使用者啟用 rewrite 後在下拉選單點「（預設）Claude Haiku 4.5」→ 表單存為 `" "`（Radix Select 不允許 `value=""`）→ 後端 `spec = model or "anthropic:claude-haiku-4-5"` 中 `" "` 為 truthy → `_parse_model_spec` 回 `("anthropic", " ")` → Anthropic API 必 400 → `rewrite_query` 的 try/except 靜默 fallback 回原始 query。**使用者以為啟用了 rewrite/HyDE，實際每輪多一次註定失敗的 LLM 呼叫且檢索永遠等同 raw**；UI 重載時 `value=" "` 又剛好匹配「（預設）」選項，完全看不出異常。
- **證據**：整條鏈無任何 trim/驗證守衛——前端 zod schema 只有 `z.string().default("")`；`onSubmit` 只對 `widget_allowed_origins` 做 trim；`bot_router.py:218` 無 validator；`update_bot_use_case.py:174-181` 直接賦值；`bot_repository.py:164` `model.query_rewrite_model or ""` 對 `" "` 無作用。
- **建議修法**：改用 sentinel value（如 `"__default__"`）並在 `onValueChange` 轉為 `""`，或 `onSubmit` 做 `.trim()`；後端加 `spec = (model or "").strip() or default` 防禦。
- **驗證狀態**：CONFIRMED（一名反駁者建議降 MEDIUM——無資料損毀或安全影響）

### H18. 閘門驗證完成後版本列表永不刷新 → 版本卡卡在「驗證中」、發布按鈕不出現
- `apps/frontend/src/pages/admin-prompt-optimizer-versions.tsx:114` + `apps/frontend/src/hooks/queries/use-config-versions.ts:95` ｜ correctness ｜ frontend-new-pages + frontend-hooks-types（同時發現）
- **失敗情境**：使用者按「送驗」→ 後端 gate run 3s 輪詢跑完（run status=completed、版本轉 `pending_publish`）→ `useGateRun` 停止輪詢並顯示完成報告，但 `useConfigVersions` 列表從未被 invalidate 也無輪詢 → `version.status` 停在 stale 的 `validating`：卡片持續轉圈、「發布上線」（需 `pending_publish`）與「強制發布」（需 `gate_verdict==="fail"`）**永遠不渲染** → Issue #54 主流程（送驗→等結果→發布）在 UI 上斷裂，toast 卻還說「結果將自動更新」。
- **證據**：`useVersionMutation.onSuccess` 只在 mutation 成功「當下」invalidate（即版本剛轉 validating 時），run 完成後不再有第二次；`useConfigVersions` 無 `refetchInterval`；`providers.tsx` `staleTime: 60_000`。全頁與 `gate-run-report.tsx` grep 不到任何 `invalidateQueries` / `useEffect` / `useQueryClient`。
- **建議修法**：`VersionCard` 加 `useEffect` 監看 `gateRun?.status` 轉為 completed/error 時 invalidate `configVersions.list(botId)` 與 detail。
- **驗證狀態**：CONFIRMED（校準：`refetchOnWindowFocus` 預設 true，使用者切走視窗再回來會刷新，故非字面上的「永遠」；兩名反駁者建議降 MEDIUM）

### H19. 影子執行授權閘 `_require_shadow_authorized` 零測試覆蓋
- `apps/backend/src/interfaces/api/agent_router.py:89` ｜ test-quality ｜ test-quality
- **失敗情境**：`config_override` 允許呼叫者以任意 system prompt 走完整對話管線，唯一防線是此函式。若未來重構把 `wants_shadow` 條件寫反、或 `_EVAL_USAGE_CATEGORIES` 誤加一般分類，任何已登入的非 admin 使用者即可注入任意 prompt 影子執行，**測試全綠不會攔截**。
- **證據**：`grep -rn "_require_shadow_authorized|shadow_authorized|X-Usage-Category" apps/backend/tests/` 零命中；`tests/integration/` 下亦 grep 不到 `config_override` / `test_mode`。`resolve_usage_context` 的角色判斷雖有 unit 測試，但「router 端 wants_shadow → 403」這條組合邏輯完全無測試。
- **建議修法**：補 agent_router integration 測試：非 admin 帶 test_mode/config_override → 403；admin 帶 `X-Usage-Category: eval_gate` → 200。
- **驗證狀態**：CONFIRMED（為 test-gap 而非 live bug；若嚴重度標尺要求「現存可利用漏洞」可降 MEDIUM）

### H20. Issue #54 全部版本 / 閘門 API 端點（473 行 router、9~10 端點）無任何 integration 測試
- `apps/backend/src/interfaces/api/bot_config_version_router.py:190` ｜ test-quality ｜ test-quality
- **失敗情境**：create/list/detail/metrics/publish/validate/replay/reject/rollback/estimate 的認證（401）、租戶隔離（404）、schema 驗證（422）、HTTP status 對映（`GatePreconditionError.http_status` → 403/409/422/429）全部只存在於程式碼。例：`_handle()` 的動態 status 對映若寫錯（429 變 500），無任何測試會紅——這正是最容易寫錯的部分。
- **證據**：`grep -rln "config_version|prompt_gate|gate_run" tests/integration/` 為空，該目錄 15 個子目錄無任何相關檔；`grep -rn "http_status" tests/` 亦無命中此對映。專案規則 `.claude/rules/python-standards.md:187` 明訂「Integration Test 覆蓋所有端點的 200/401/404/422」。
- **建議修法**：為 `bot_config_version_router` 補 `httpx.AsyncClient` integration 測試，至少覆蓋 publish/rollback/validate 的 200/401/404 與 precondition error 的 status code 對映。
- **驗證狀態**：CONFIRMED

---

## MEDIUM

> 為控制篇幅，MEDIUM 各項採緊湊格式；每項仍含 file:line、分類、失敗情境、證據、修法、驗證狀態。

### M1. create version 的 `changes` 值零型別驗證：非字串 prompt 欄位直接 500
`apps/backend/src/interfaces/api/bot_config_version_router.py:52` ｜ correctness ｜ prompt-gate-core
**情境**：`POST /config-versions {"changes":{"bot_prompt":123}}` → `check_prompt` 中 `123` 為 truthy → `_TEMPLATE_VAR_RE.finditer(123)` 拋 `TypeError` → 未被任何 handler 分類 → 500。另 `{"max_tool_calls":-5}` 等型別正確但超範圍的值全程無驗證直寫進 bots 表。
**證據**：`changes: dict[str, Any]` 僅檢查 key ∈ SNAPSHOT_FIELDS（`version_use_cases.py:78-81`）；`static_checks.py:104` `check_prompt(text or "")` 對 int 不會被 `if not text` 攔下；`config_snapshot.py:151` `setattr`、:157 `replace(bot.llm_params, **changes)` 無驗證。修正：`temperature:"hot"` 會被 Float 欄位擋下（另一個 500），不會靜默存入。
**修法**：`CreateVersionRequest.changes` 改用 typed Pydantic schema，或在 use case 逐欄位驗型別與範圍。｜CONFIRMED

### M2. `next_version_no` 用 MAX+1 取號無並發防護 → 撞 `uq_bcv_bot_version` 500
`apps/backend/src/infrastructure/db/repositories/bot_config_version_repository.py:131` ｜ correctness ｜ prompt-gate-core
**情境**：兩位管理員（或前端 double-click）同時建版 → 兩者 SELECT MAX+1 得同號 → 後者 IntegrityError 未被捕捉 → 500 而非 409/重試。
**證據**：取號（`version_use_cases.py:104`）與 INSERT（:114）分屬不同交易，無鎖無 retry；全 repo 無 `IntegrityError` handler。
**修法**：取號併入 INSERT，或捕捉 IntegrityError 重試/轉 409；長期用 per-bot advisory lock。｜CONFIRMED（兩名反駁者建議降 LOW——需真正同時、blast radius 僅失敗請求）

### M3. 版本狀態轉移無樂觀鎖：並發 publish + reject 可寫出 `published → rejected`
`apps/backend/src/infrastructure/db/repositories/bot_config_version_repository.py:47` ｜ correctness ｜ prompt-gate-core
**情境**：版本處於 pending_publish，publish 與 reject 並發：兩者各讀到獨立 entity 副本、記憶體 guard 皆過；A 完成發布後 B 的 save 無條件覆寫 `status='rejected'` → DB 出現 entity 明文禁止的轉移，bots 表仍跑著該版本設定。
**證據**：update 路徑無 expected-status 條件、無 version/etag 欄位、`find_by_id` 無 `with_for_update()`。**修正**：`is_current` 不會被重設為 False（SQLAlchemy 比對 committed_state 會略過未變更欄位），故實際殘留是「status=rejected 但 is_current=TRUE」的不一致，非 `find_current` 回 None。
**修法**：save 改條件式 UPDATE（`WHERE status=<讀取時狀態>`，rowcount=0 即 raise），或 `SELECT FOR UPDATE`。｜CONFIRMED（部分後果修正，兩名反駁者建議降 LOW）

### M4. `asyncio.create_task` 回傳值未保留 → 背景 gate/replay task 可能被 GC，版本無聲卡死 validating
`apps/backend/src/application/prompt_gate/gate_run_use_cases.py:255`（`replay_use_cases.py:186` 同）｜ correctness ｜ prompt-gate-background
**情境**：CPython 官方文件明載需自行保存 `create_task` 回傳值。task 若被 GC：直接消失、無 exception/log、except 不執行 → run 永停 running、版本永卡 validating（無法再 validate/publish/reject）。對照 optimizer run 有 `RunManager.set_task` 保存引用。
**證據**：全 repo 無任何地方保存這兩個 task 的引用。
**修法**：存進 module/實例層級 set 並在 done callback 移除（並 log `task.exception()`）。｜CONFIRMED（兩名反駁者均建議降 LOW——await I/O 期間 transport callback 鏈實際持有強引用，且此為 codebase 既有普遍慣例）

### M5. 孤兒清理只看 run 狀態不看版本狀態 → 版本永久卡 validating 無救援路徑
`apps/backend/src/application/prompt_gate/gate_run_use_cases.py:398` ｜ correctness ｜ prompt-gate-background
**情境**：`_save_background` 是同一 session 兩個獨立 atomic commit：`gate_repo.save(run)` 成功、`version_repo.save(version)` 失敗（或進程在兩次 commit 間被 SIGKILL，Cloud Run 換版/縮容的常態）→ DB 最終狀態 run=completed、版本=validating → `mark_orphans_error` 只撈 `status ∈ {queued, running}` 的 run，永遠撈不到 → 該版本三個 API 全 409，**無任何 API 可解**。附帶：except 裡 `run.mark_error` 無狀態守衛，會把已 completed 的 run 無條件改寫成 error。
**修法**：清理改為「revert 所有 validating 且對應 run 非 running 的版本」；兩筆寫入合併為單一交易；`mark_error` 加狀態守衛。｜CONFIRMED

### M6. `StartGateRun` 無並發互斥：同版本兩個併發 POST 都通過，日限額亦可超額
`apps/backend/src/application/prompt_gate/gate_run_use_cases.py:251` ｜ correctness ｜ prompt-gate-background
**情境**：連點兩下驗證按鈕 → 兩邊各讀到 draft、記憶體 `mark_validating` 皆成功、save 為無條件覆寫 UPDATE → 兩個背景 run 同跑同一版本，token ×2；先完成者轉版本狀態，後完成者 `mark_validation_result` 拋 `InvalidVersionTransitionError` → 已算完的結果被改寫為 run error。`count_today` 同為讀後寫，可突破 `gate_daily_limit`。
**證據**：`bot_config_version_versions` 只有 `uq_bcv_bot_version` 與 `ix_bcv_current` 兩個唯一約束，無任何可擋「同版本同時進 validating」的限制。
**修法**：狀態轉移改條件式 UPDATE（`WHERE status='draft'`，rowcount=0 → 409）；日限額改在 insert 同交易內以 `SELECT FOR UPDATE` 防重。｜CONFIRMED

### M7. 多實例／滾動部署時新實例的孤兒清理會殺掉其他存活實例上進行中的 gate run
`apps/backend/src/main.py:120` ｜ correctness ｜ prompt-gate-background
**情境**：Cloud Run 部署新 revision（或 autoscale 拉起第二實例）→ 新實例 lifespan 無條件把 DB 中所有 queued/running run 標 error、validating 版本退回 draft，**包含舊實例上仍健康執行中的 run** → 舊實例燒完全部 token 後 `mark_validation_result` 因版本已退回 draft 拋錯 → 全額 token 白燒 + 兩實例狀態互踩。
**證據**：`prompt_gate_run_repository.py:100-120` 無 instance 識別、無 `started_at` 寬限、無 heartbeat 欄位；`deploy-backend.yml` flags 含 `--min-instances=1 --max-instances=5`，Cloud Run 換版時舊 revision 仍在服務。與已知債「重啟中斷自己進程的 run」是不同事件。
**修法**：清理加 `started_at` 寬限（只清超過 max 預期時長者）或記錄 instance_id 只清自己的遺留。｜CONFIRMED

### M8. `test_mode` 影子執行在 stream 例外分支仍將 trace 持久化到生產表
`apps/backend/src/interfaces/api/agent_router.py:325` ｜ correctness ｜ shadow-exec-isolation + agent-pipeline（同時發現）
**情境**：Playground 對照測試以 `test_mode=true` 走 `/chat/stream`，agent 執行中拋例外（LLM timeout、Milvus 斷線）→ router except 分支呼叫 `_persist_agent_trace(...)` **未傳 persist 參數**（預設 True）→ 影子 trace（outcome=failed、tenant_id、bot_id）寫入生產 `agent_execution_traces`，汙染 admin 觀測頁與版本成效統計。
**證據**：正常路徑三處（:842/:962/:1120）都有 `persist=not command.test_mode`，唯獨此例外分支漏帶；`agent_trace_model` 對 conversation_id 無 FK，故 bogus id 不會讓 insert 失敗——這一列真的會落庫。
**修法**：例外分支改為 `persist=not command.test_mode`。｜CONFIRMED（實際觸發路徑僅 Playground stream，gate/optimizer 走非 stream，反駁者建議降 LOW）

### M9. `config_override` / `history_override` 可與 `test_mode=False` 併用 → 影子輸出寫入生產對話且版本歸因錯誤
`apps/backend/src/interfaces/api/agent_router.py:98` ｜ correctness ｜ shadow-exec-isolation
**情境**：授權 admin client 帶合法 eval header 但送 `{config_override: draft快照, test_mode: false}`（client 端漏設旗標）→ `wants_shadow` 是三旗標 OR，只驗授權不強制 test_mode → (1) draft 設定產生的回答被當真實對話持久化並觸發 memory 萃取與線上 eval；(2) usage 仍被打標為「當前線上版本」的 `config_version_id`，草稿的品質/token 計入線上版本；(3) `history_override` 只在 test_mode 分支被消費，此時被靜默忽略，多輪語境測試實際跑在 DB 歷史上。
**修法**：`config_override` 或 `history_override` 存在時強制（或隱式設定）`test_mode=True`，否則 422；至少 `config_override` 生效時不打 `config_version_id`。｜CONFIRMED（目前所有內部呼叫端一律 `test_mode=True`，屬 defense-in-depth 缺口，反駁者建議降 LOW）

### M10. stream 路徑 guard 攔截分支的 `done` 事件缺 `trace_id` / `trace_nodes`
`apps/backend/src/application/agent/send_message_use_case.py:962` ｜ correctness ｜ agent-pipeline + shadow-exec-isolation（同時發現）
**情境**：Studio / Playground 走 stream 送出被 input guard 攔截的訊息 → guard 分支呼叫 `_persist_agent_trace` 但**丟棄回傳的 (trace_id, nodes)**，接著 `yield {"type":"done"}` 不帶任何 trace 欄位 → 前端拿不到 trace_id，無法 fetch 剛特意持久化的 `guard_input_blocked` DAG（該段註解宣稱的目的落空）；test_mode 下 trace 本就不落庫，資訊全失。
**證據**：正常結束路徑（:1171-1176）與非 stream 的 `_check_input_guard`（:1228-1244）都有回傳；前端 `use-studio-streaming.ts:107-108` 是取得 DAG 的唯一觸發點。
**修法**：攔截分支接住 `(trace_id, nodes)`，done 事件比照正常路徑帶上。｜CONFIRMED

### M11. 生產程式碼殘留 `test-back` 測試觸發器：任何登入使用者可偽造後端錯誤事件並觸發告警
`apps/backend/src/interfaces/api/agent_router.py:244` ｜ security ｜ **shadow-exec-isolation + usage-attribution + agent-pipeline + security-injection（四個 finder 同時發現）**
**情境**：任一有效 JWT 使用者 `POST /api/v1/agent/chat/stream {"message":"test-back"}` → 進入自陳 `--- TEST TRIGGER: remove before production ---` 的分支 → 偽造 RuntimeError（含假 Milvus traceback、`status_code=500`、tenant_id 取自 JWT）寫入 `error_events`，並 `asyncio.create_task(dispatch_error_notification(event))` → 可重複呼叫線性灌爆錯誤事件表、淹沒 admin 錯誤儀表板、掩護真實事故。
**證據**：端點只有 `Depends(get_current_tenant)`，無 role 檢查、無 env flag；`_require_shadow_authorized` 只管三旗標與訊息內容無關。**影響修正**：通知端有 `RedisNotificationThrottle` 以 fingerprint SETEX 去重，故「刷爆告警」被大幅削弱（但 `redis_throttle.py:21-22` `except RedisError: return False` 為 fail-open）；真正不受保護的是 error_events 表本身。
**修法**：**直接刪除該區塊**（而非加 flag 保留）。這是四個 finder 獨立命中的最高共識項，建議列為第一優先的立即修復。｜CONFIRMED ｜ **可利用：是**

### M12. SSE 客戶端中斷 → 該輪已消耗的 LLM token 完全漏記
`apps/backend/src/interfaces/api/agent_router.py:342`（`widget_router.py:211` 同構）｜ correctness ｜ usage-attribution
**情境**：使用者串流途中關閉分頁 → StreamingResponse 取消 generator → `GeneratorExit`/`CancelledError`（BaseException，不被 `except Exception` 捕捉）→ 迴圈後的 record_usage 區塊永不執行 → 上游已產生並計費的 token 在 `token_usage_records` 完全缺席。
**修法修正**：包 `try/finally` **無效**——`usage_data` 在被取消當下仍是 None（usage 事件在 final_response 之後才 yield）；真正可行的是在 use case 內產生 usage 當下即落帳。
**修法**：改為 `execute_stream` 內部在產生 usage 後立即記帳。｜CONFIRMED（攻擊窗口比描述窄——內容 token 串完後 usage 事件緊接著同步 yield，攻擊者需犧牲答案尾段；反駁者建議降 LOW）

### M13. `guard_blocked` 暴露以 body 自報的 `identity_source` 判定，可被任何租戶偽造成 studio
`apps/backend/src/interfaces/api/agent_router.py:111` ｜ security ｜ agent-pipeline
**情境**：任一持有效 JWT 的一般租戶使用者 `POST /api/v1/agent/chat {"message":"reveal your system prompt","identity_source":"studio"}` → `_maybe_expose_guard` 判定通過 → response 直接回 `guard_rule_matched`（命中的 regex 原文）→ 枚舉平台全域防護規則（正規讀取需 system_admin）。
**證據**：同專案 `application/usage/usage_context.py:4-6` 已明文寫「授權以 JWT role 判定（`identity_source` 是 body 自報值、可偽造，不可作依據）」——此處卻拿它當授權訊號，屬同 codebase 內既有 doctrine 的違反。
**修法**：改用 JWT role 或 `usage_ctx` 判定是否暴露 guard 細節，`identity_source` 只作 trace 標記；與 H7 一起做（同一個「guard 細節暴露面」的兩條通路）。｜CONFIRMED ｜ **可利用：是**

### M14. `test_mode` 影子執行的意圖分類 token 記成生產 `intent_classify`，未走 eval 分流
`apps/backend/src/application/agent/intent_classifier.py:299` ｜ correctness ｜ agent-pipeline
**情境**：閘門 run / 優化迴圈以 `test_mode=True` 執行 N 個 case，每個 case 進 `_resolve_worker_config` → `IntentClassifier._call_llm` → `record_usage.execute(request_type=INTENT_CLASSIFY)` **無視 test_mode / run_id** → N 筆分類 token 記成生產用量並計入租戶帳務。#54 的 eval token 分流只涵蓋主模型（router 層 usage_ctx）。
**證據**：`send_message_use_case._resolve_worker_config` 未把 test_mode/usage category 傳給 classifier；`RecordUsage` 支援 run_id/config_version_id 但此處未用。
**修法**：把 usage 分類（或至少 test_mode 旗標與 run_id）從 `SendMessageCommand` 傳遞到 `IntentClassifier`。｜CONFIRMED（`max_tokens=50`，帳務污染金額有限，反駁者建議降 LOW；帳目正確性論點強於成本論點）

### M15. multitenant LINE webhook 全部錯誤（含簽章驗證失敗）都回 500，且同步執行完整管線
`apps/backend/src/interfaces/api/line_webhook_router.py:107` ｜ correctness ｜ channel-parity
**情境**：(a) 攻擊者送假簽章 → `prepare_and_reply` raise `ValueError` → 非 DomainException → 全域 handler 回 **500**（舊端點是 403）；(b) 任何處理例外（LLM timeout、M18 的 KeyError）→ 500 → LINE redelivery 重送同一事件 → 重複 LLM 呼叫與重複回覆；持續錯誤會讓 LINE 停用 webhook。舊端點用 `background_tasks` + `safe_background_task` 先回 200，兩個 LINE 端點行為自相矛盾。
**修法**：簽章/bot 查驗失敗改回 403/404（改拋 DomainException），驗簽後把 `process_and_push` 丟 background task 先回 200。｜CONFIRMED（LINE redelivery 為 console 可開關選項，「必定重複」屬條件性）

### M16. 快速道文字檢索忽略 worker per-tool RAG 參數，只用 bot 全域 top_k/threshold
`apps/backend/src/application/line/handle_webhook_use_case.py:381` ｜ correctness ｜ channel-parity
**情境**：direct_retrieval worker 在 `tool_configs["rag_query"]` 設 `rag_score_threshold=0.3`（bot 全域 0.7）→ 快速道用 0.7 判定 → 0.3~0.7 分的命中被判「未過門檻」→ 不必要升級完整 ReAct（快速道形同虛設）；反向設定則低品質 chunk 直接注入生成。同一 worker 在完整 ReAct 路徑行為正確 → 快速道與升級路徑檢索結果不一致。
**證據**：`tool_rag_params` 已傳入（L327）卻只在 DM 工具用到（L359-371），`rag_query` 的 resolved 參數從未讀取；`resolver` 回傳的 `kb_ids` 覆寫同樣未被使用（缺口比描述再大一點）。
**修法**：快速道改讀 `(tool_rag_params or {}).get("rag_query")` 的 `rag_top_k`/`rag_score_threshold`/`rerank_*`，缺時退回 bot 全域。｜CONFIRMED

### M17. worker `temperature` / `max_tokens` 覆蓋條件兩通路不一致
`apps/backend/src/application/agent/send_message_use_case.py:619` ｜ correctness ｜ channel-parity
**情境**：worker 不指定 provider/model（沿用 bot 模型）但把 temperature 調成 0.1、max_tokens 調成 300 → LINE 無條件套用生效；web/widget 整個 llm_params 覆蓋被 `if matched.llm_provider or matched.llm_model:` 跳過 → 仍用 bot 值。同一 worker 設定在兩通路產生不同取樣參數與回覆長度，違反「三通路行為一致」驗收條件。
**證據**：`worker_config.py:21-22` temperature/max_tokens 為非 Optional 實欄位（預設 0.7/1024），故差異是雙向的：web 完全忽略 worker 值，LINE 連 worker 從未調整過的預設值也會蓋掉 bot 設定。
**修法**：web 端把 temperature/max_tokens 賦值移出 provider/model 條件。｜CONFIRMED

### M18. LINE 事件解析對無 `userId` 的 message event（群組/未同意條款）直接 KeyError → 整包 webhook 500
`apps/backend/src/application/line/handle_webhook_use_case.py:222` ｜ correctness ｜ channel-parity
**情境**：bot 被拉進群組或使用者未同意 LINE 官方帳號條款時，message event 的 source 可能只有 `groupId`/`roomId` → `event_data["source"]["userId"]` KeyError → **整批事件解析失敗** → 500 → LINE redelivery，同批次中其他正常 1:1 訊息也一起卡死無人得到回覆。
**證據**：直接下標無 `.get()` 也無 `source.type` 過濾；一批 events 共用一次解析，單一壞事件毒殺全批；`line_webhook_router.py:29` 為同一份複製。
**修法**：改 `event_data["source"].get("userId")`，缺 userId 或 `source.type != "user"` 的事件跳過。｜CONFIRMED

### M19. LINE 意圖分類 `router_model` 缺 tenant default fallback（S-KB-Followup.2 只做了 web）
`apps/backend/src/application/line/handle_webhook_use_case.py:694` ｜ correctness ｜ channel-parity
**情境**：租戶設 `default_intent_model=gpt-4o-mini`、`bot.router_model` 留空 → web/widget 分類用租戶預設；LINE 傳空字串 → 用系統預設 LLM。同一 bot 兩通路分類模型不同，準確率/延遲/成本不一致。
**證據**：`send_message_use_case.py:352-365` 有完整 fallback 鏈（含 `tenant_repo.find_by_id`）；`HandleWebhookUseCase` 未注入 `tenant_repository`（`container.py:2489-2517`），技術上也無法做同一 fallback。`domain/bot/entity.py:142` 註解「空 = tenant default → 系統 default」證明 LINE 違背欄位自身語義。
**修法**：注入 `tenant_repository` 並套用同一 fallback 鏈。｜CONFIRMED

### M20. LINE trace 持久化缺 `outcome` 欄位 → 全部 LINE trace outcome=NULL，失敗率儀表板排除 LINE
`apps/backend/src/application/line/handle_webhook_use_case.py:964` ｜ correctness ｜ channel-parity
**情境**：LINE 對話中工具失敗 → web 路徑 trace row 標 `outcome="failed"` 進入失敗率統計；LINE 路徑 outcome 恆 NULL → 以 outcome 過濾的觀測查詢（`ix_traces_outcome_created` 索引路徑）看不到任何 LINE trace，**POC 主力通路的異常監控失明**。
**證據**：LINE 建 `AgentExecutionTraceModel` 的 kwargs 逐一比對後確實缺 outcome（欄位 nullable 故不報錯）；web 版 `_persist_agent_trace` 有 `outcome = _compute_trace_outcome(node_dicts)`。
**修法**：LINE trace 補算 `_compute_trace_outcome`，或按絞殺者計畫優先合併兩份 `_persist_agent_trace`。｜CONFIRMED

### M21. 長期記憶（memory load/extraction）只存在 web/widget 管線，LINE 完全未接
`apps/backend/src/application/line/handle_webhook_use_case.py:109` ｜ quality ｜ channel-parity
**情境**：`bot.memory_enabled=True` 的租戶：widget 訪客的偏好被抽取並在後續注入 history_context；同一 bot 的 LINE 使用者（有穩定 user_id，**本是 memory 最適用的通路**，`SendMessageCommand` 註解也明列 `"line"`）每輪既不載入也不抽取記憶——功能開關對 LINE 靜默無效，且 `channel-parity.md` 六項已知債未含 memory。
**證據**：`grep -n memory handle_webhook_use_case.py` 回傳 0 筆；container 亦未注入。
**修法**：LINE 路徑接上 `resolve_identity(source="line", external_id=user_id)` + load/extract memory，或在 `channel-parity.md` 債務清單明列並排期。｜CONFIRMED

### M22. 閘門 replay 回放 LINE 真實流量卻走 web 影子管線
`apps/backend/src/application/prompt_gate/replay_use_cases.py:262` ｜ quality ｜ channel-parity
**情境**：LINE-only bot 發布前跑 replay：`find_recent_user_questions` 抽到的全是 LINE 問題（該查詢不分通路），但影子執行走 `/agent/chat` → 無 `LINE_CHANNEL_PROMPT_SUFFIX`（格式/長度/角色鎖）、無 direct_retrieval 快速道、用 `classify_workers` 而非 `classify_sanitize` → **baseline 與 candidate 的對比來自一條沒有任何真實使用者在走的管線**，pairwise 勝負與線上實際回覆可系統性不同。
**修法**：至少在 replay 影子請求註入 LINE channel suffix（或以能力旗標讓影子執行模擬來源通路），並在閘門結果標注「以 web 管線近似」的限制。｜CONFIRMED（屬 fidelity 限制而非崩潰型 bug）

### M23. LINE Channel Secret / Access Token 明文落庫且 API 回應不遮罩
`apps/backend/src/infrastructure/db/models/bot_model.py:181` ｜ security ｜ security-injection
**情境**：建立/更新 Bot 時兩個憑證走 `_DIRECT_FIELDS` 直接 `setattr`，未經 `encryption_service`；DB 欄位為純 `String(255)`。任何 DB dump、備份外流或 `GET /bots/{id}`（原值回傳）都直接暴露可冒充官方帳號的憑證。
**證據**：`grep line_channel_secret` 全 src 15 處命中無任何一處接觸 encryption/decrypt；對照同檔 `mcp_bindings.env_values` 有 AES 加密且回應以 `"***"` 遮罩。**額外提醒**：`infra/setup-worker-vm.sh:40` 把一把真實樣態的 `ENCRYPTION_MASTER_KEY` 硬編碼進版控，改走加密時必須一併換金鑰管理。
**修法**：LINE 憑證比照 mcp env_values 走 AES 加密落庫、讀取時解密；API 回應改為遮罩或不回傳。｜CONFIRMED ｜ **可利用：是**（獨立看是租戶內過度暴露——bot_router 無 role gate，任何 `role="user"` 成員即可讀走；與 C8 疊加後等同 CRITICAL）

### M24. JWT secret 與加密 master key 皆有硬編碼 fallback（部署漏設即 fail-open）
`apps/backend/src/config.py:24` ｜ security ｜ security-injection
**情境**：未設 `JWT_SECRET_KEY` 時預設 `'dev-secret-key-change-in-production'` → 攻擊者用此公開已知字串以 HS256 自簽 `role=system_admin` 的 token 完全繞過認證。`encryption_master_key` 未設時 fallback 為 `'0'*64`，mcp env_values 等同未加密。無任何啟動時 fail-closed 檢查。
**證據**：`apps/backend/.env.example:22` 直接寫入該預設值並散佈；`deploy-backend.yml:75` 若 GitHub secret 未設只會展開成空字串（同樣可預測），流程不會失敗；`app_env` 從未被用於守衛此事。
**修法**：`app_env` 非 development 時，於啟動 assert 兩個 key 已由環境覆寫且非預設值，否則拒絕啟動。｜CONFIRMED ｜ **可利用：是（條件式）**（依賴部署 misconfig；在此 codebase 中因其他認證缺口而顯得冗餘，但自架/dev-vm 環境完全可偽造）

### M25. `RollbackResponse` 遺失 `version_id` / `published` / `note` → 被閘門攔下的 rollback 看起來像已生效
`apps/backend/src/interfaces/api/prompt_optimizer_run_router.py:106` ｜ correctness ｜ eval-dataset
**情境**：租戶開啟閘門後執行 optimizer rollback → use case 建 draft、publish 被 `GateBlockedError` 攔下，回傳 `{applied: True, published: False, note: "...發布被閘門攔下", version_id: ...}` → pydantic v2 預設 `extra=ignore` 把三個欄位靜默丟棄 → 前端只看到 `applied=true`，使用者以為 prompt 已還原上線，**實際線上未變、draft 卡在待發布**。
**修法**：`RollbackResponse` 補 `version_id: str|None`、`published: bool`、`note: str` 三欄。｜CONFIRMED

### M26. `EstimateCostUseCase` 讀取不存在的 `SystemPromptConfig.base_prompt` → token breakdown 永遠退回 500 fallback
`apps/backend/src/application/eval_dataset/eval_use_cases.py:344` ｜ correctness ｜ eval-dataset
**情境**：`POST /estimate` 帶 bot_id → `sys_config.base_prompt` 觸發 AttributeError（`SystemPromptConfig` 只有 id/system_prompt/updated_at）→ 被廣域 except 吃掉 → `prompt_tokens` 一律 fallback 500，已算出的 `bot_prompt` 實際長度也一起丟失 → **「依真實 prompt 長度估價」的功能對所有 bot 靜默失效**，長 prompt 的成本估算大幅低估。
**證據**：全 repo `base_prompt` 存在於 Bot entity 但從不在 `SystemPromptConfig` 上——作者複製錯屬性；`container.py:2241-2249` 永遠注入該 repo，故每個帶 bot_id 的 estimate 都會走到。
**修法**：改為 `sys_config.system_prompt`，並把 except 縮小範圍避免再度靜默吞錯。｜CONFIRMED

### M27. `ListRunsUseCase` 分頁合併錯誤 → active run 每頁重複、每頁尾端 DB run 被永久截掉
`apps/backend/src/application/eval_dataset/run_use_cases.py:647` ｜ correctness ｜ eval-dataset
**情境**：1 個進行中 run + 40 筆歷史、page_size=20：page 1 = active + DB#0-19 共 21 筆 → `merged[:limit]` 截掉 DB#19；page 2 的 offset 從 #20 開始 → **DB#19 在任何頁都看不到**，且 active run 在每頁重複出現。`count()` 又把 active 數量加總，total 與可見項不一致。
**修法**：active runs 只併入第一頁（offset==0），DB limit 改為 `limit - len(active)`，或合併後再統一分頁。｜CONFIRMED

### M28. 驗證/單次 eval 把 API 呼叫失敗偽造成 0 分 → 認證過期或後端故障產生假 FAIL 並落歷史
`apps/backend/src/application/eval_dataset/eval_use_cases.py:530` ｜ correctness ｜ eval-dataset
**情境**：`/validate` 跑到一半 JWT 過期（建構 AgentAPIClient 時不帶 refresh_token——與優化 run 行為分歧）或後端 5xx → 每題 except 塞入 `answer=""` 的 ChatResult → assertions 全掛 → 該輪全部 case 記 0 分 → `verdict=FAIL` 連同 unstable/p0_failures 寫進 run 歷史，**與真實品質失敗無法區分**。使用者據此判定 prompt 不合格，實際只是 token 過期。
**修法**：API 例外的 case 標記為 error 而非 0 分（或錯誤率超閾值時整輪作廢回 502），並比照優化 run 傳 refresh_token。｜CONFIRMED

### M29. 啟動時 `pricing_cache.refresh()` 未包 `independent_session_scope` → tracked session 永不關閉並汙染 cleanup task context
`apps/backend/src/main.py:131` ｜ correctness ｜ session-lifecycle
**情境**：每次 process 啟動：lifespan 執行 refresh → `get_tracked_session()` 在 lifespan context 建 session 並 set ContextVar → 裸 SELECT 開交易 → 無人 rollback/close → 每次啟動固定漏 1 條 pool 連線；且 `asyncio.create_task(_log_cleanup_loop)` 複製此 context，**cleanup loop 直接繼承這顆已死 session**，把 H14 的故障放大為「從第一次就失敗」。
**證據**：同 lifespan 內上方的 gate 孤兒清理（L120）與 seed（L103）都有正確處理，唯獨此段沒有。
**修法**：startup refresh 包 `async with independent_session_scope():`，或讓 `InMemoryPricingCache` 改吃 session factory 自建自關。｜CONFIRMED

### M30. arq worker 所有 job 經 `get_tracked_session` 建 session 但無任何關閉機制
`apps/backend/src/worker.py:294` ｜ correctness ｜ session-lifecycle
**情境**：以 SELECT 結尾的 job（每分鐘一次的 `conversation_summary_scan_task`：`find_pending_summary` 後直接 return）留下開著交易的 checked-out 連線，只能等 task 結束後 GC 讓 SQLAlchemy 以 terminate 方式回收 → 生產環境每分鐘 1-2 次連線建立/強制終結的 churn。另 read→長 LLM→write 型 job（`process_conversation_summary_task`，job_timeout 600s）若 LLM 段超過 120s，連線被 idle-in-transaction 砍掉，後續 `record_usage` 寫入直接失敗。
**證據**：worker.py / worker_resilience.py grep 不到 `independent_session_scope` 或 `session.close`；`_new_container()` 只是新建 Container，不 reset ContextVar；`WorkerSettings` 無 job 收尾 hook；`SessionCleanupMiddleware` 只在 HTTP scope 生效。
**修法**：在 `execute_with_resilience`（或各 task 的 `_inner`）以 `async with independent_session_scope():` 包住 use case 執行。｜CONFIRMED

### M31. Validate 路徑同樣漏合併 `default_assertions`，PASS 判定未含資料集預設斷言
`apps/backend/src/application/eval_dataset/eval_use_cases.py:485` ｜ correctness ｜ optimizer-package
**情境**：使用 validate（N 次重跑 → PASS/FAIL 判定）的 dataset 帶有 `default_assertions` → 建 TestCase 只帶 `tc.assertions`，Evaluator 不讀 dataset 層 defaults → **一個違反預設安全斷言的 prompt 仍得到 PASS verdict**，與 gate run 判定互相矛盾。同檔 `RunSingleEvalUseCase`（:50-84）有完全相同的漏洞。
**修法**：同 H16——建 TestCase 時把 `dataset.default_assertions` 併進每個 case。｜CONFIRMED（與 H16 為同一根因、不同檔案，建議一次修三處）

### M32. Validate 評估完全忽略 `conversation_history`，多輪 case 必然誤判失敗
`apps/backend/src/application/eval_dataset/eval_use_cases.py:525`（CLI `__main__.py:245` 同）｜ correctness ｜ optimizer-package
**情境**：dataset 含多輪 case（例如問題是「那第二個方案呢？」搭配 `references_history` 斷言）→ validate 的 `_eval_fn` 只送 `tc.question`，不帶 `history_override` 也不做逐句 warm-up → bot 無上下文回答 → 每一輪 repeat 都 fail → P0 多輪 case 直接導致整體 FAIL（誤判）。
**證據**：`api_client.chat` 明確支援 `history_override` 參數（非能力限制）；gate run（`gate_run_use_cases.py:512-518`）與優化 runner（`runner.py:302-336`）都有處理，唯 validate 缺漏；內建 dataset（`_security_base.yaml`、`_prompt_injection_advanced.yaml`、`joyinkitchen.yaml`）皆含多輪題。
**修法**：validate 的 `_eval_fn` 傳 `history_override=list(tc.conversation_history) or None`（CLI 版同步修）。｜CONFIRMED

### M33. `run_assertion` 對非法/缺漏 params 拋 TypeError → 整個 gate run / 優化 run 崩潰而非單一斷言失敗
`apps/backend/prompt_optimizer/assertions.py:73` ｜ correctness ｜ optimizer-package
**情境**：使用者透過 dataset API 存了 params 有 typo 的斷言（如 `{"type":"max_length","params":{"maxChars":100}}`）——loader 只驗 type 不驗 params，DB 建立路徑完全沒驗 → 評估時 `fn(ctx, **params)` 觸發 TypeError → gate run 的 `_assert_case` 無 try/except → 例外傳到背景 except → **一顆壞 case 使整批 gate run 標記 background_error**；優化 run 同理崩潰整個 run。
**證據**：26 個斷言函式簽名一律 kw-only 且無 `**kwargs`；unknown type 有 graceful 回傳（:66-72）而 bad params 沒有；`gate_run_use_cases.py:560` 只 `params.pop("severity", None)` 顯示已知 kw-only 會炸卻不設防；`datasets/_schema.json` 對 assertion 只 `required: ["type"]`。
**修法**：`run_assertion` 包 try/except TypeError 回傳 `passed=False` 的 AssertionResult，並在 dataset 建立時用各斷言簽名驗 params。｜CONFIRMED

### M34. CLI 直連模式：迭代中途例外會把未審核的候選 prompt 留在線上表
`apps/backend/prompt_optimizer/runner.py:198` ｜ correctness ｜ optimizer-package
**情境**：CLI 帶 `--db-url` 跑優化（`write_prompt` 直寫 bots 表）→ 第 i 輪已寫入候選 → 下一輪 `mutator.mutate()` 內 `llm.ainvoke` 遇 rate limit/網路錯誤（無 try/except）或 Ctrl-C → run 中止，最終的 `write_prompt(target, best_prompt)`（:266）永不執行 → **線上 bot prompt 停留在上一輪已被 DISCARDED 或未評完的 LLM 變異版本**，無任何還原。
**證據**：:198 寫候選、:266 才寫回 best，之間無 try/finally；`__main__.py:145-150` 的 finally 只 close client 不回寫 prompt。API 路徑因 write 只寫記憶體 prompt_store 不受影響。
**修法**：優化迴圈包 try/finally，finally 一律回寫 `best_prompt`（或至少 baseline），並在 `mutate` 的 ainvoke 周圍加例外重試。｜CONFIRMED

### M35. `import_dataset` 存入已合併 defaults 的 case 斷言，`read_dataset` 又再合併一次 → 斷言重複、分數失真
`apps/backend/prompt_optimizer/db_client.py:216` ｜ correctness ｜ optimizer-package
**情境**：`import --file ds.yaml` 後再 `run --dataset-id <id>`：YAML 載入時 `_parse_cases` 已把 defaults 併進每個 case，`import_dataset` 把這份「已含 defaults」的斷言寫進 `eval_test_cases`；`read_dataset` 讀回時又疊一次 → 每個 default 斷言跑兩次。例：case 有 2 defaults + 1 專屬，專屬 fail 時真實分數 2/3=0.67，實跑變 4/5=0.80——**分數被灌水，優化迴圈的 accept/discard 判斷跟著失真**。
**證據**：對照 `dataset_to_yaml:239-246` 與 `eval_dataset_router.py:383-390` 都有 default_set 過濾，唯獨 `db_client.import_dataset` 沒有。
**修法**：import 寫入 case 斷言時剔除 defaults，或 read 不再重複合併。｜CONFIRMED（僅 CLI import→CLI run 路徑）

### M36. `PromptDBClient` 讀寫 prompt 完全忽略 `target.tenant_id`，僅以 bot_id 定位
`apps/backend/prompt_optimizer/db_client.py:58` ｜ security ｜ optimizer-package
**情境**：`PromptTarget` 帶有 tenant_id 欄位但 `read_prompt` / `write_prompt` 的 WHERE 只有 `id = :bot_id`。攻擊者以自己租戶帳號 `POST /datasets` 把 `body.bot_id` 填被害租戶的 bot_id（`create_dataset` 完全不驗 bot 歸屬），再 `POST /runs` → 背景任務讀出被害 bot 的 `bot_prompt`/`base_prompt` → 該值以 baseline 寫進攻擊者可見的 run `prompt_snapshot` / `/diff` → **他租戶 system prompt（商業機密/防護規則）外洩**。
**證據**：`_TARGET_MAP` where 模板 bot 層一律 `"id = :bot_id"`；`config.py:14-18` 的 tenant_id 欄位形同虛設。寫入方向不成立（API 路徑 write 只寫記憶體 prompt_store，rollback 走 `CreateConfigVersionUseCase` 有租戶檢查）。
**修法**：bot 層 where 改為 `id = :bot_id AND tenant_id = :tenant_id`（tenant_id 空時拒絕執行），rowcount=0 視為找不到；`create_dataset` 一併驗證 bot 歸屬。｜CONFIRMED ｜ **可利用：是**（兩名反駁者建議由原 LOW **上修**；可利用性評估者定為 MEDIUM——需先知道 bot_id 或 dataset_id）

### M37. Playground 對照 dialog 無 AbortController：關閉 dialog 無法中止兩條 SSE 影子串流
`apps/frontend/src/features/bot/components/playground-compare-dialog.tsx:151` ｜ correctness ｜ frontend-new-pages
**情境**：使用者送出訊息（同時起兩條影子串流）後立刻關閉 dialog 或離開頁面 → `fetchSSE` 未傳 AbortSignal，兩條串流在背景繼續讀完整個回應 → 後端持續生成、token 照計入租戶用量；使用者以為關窗即停止消耗。
**證據**：`lib/sse-client.ts:3-19` 的 `fetchSSE` 簽章完全不接受 signal；dialog 的 `onOpenChange` 只切 open prop 無 cleanup；`bot-detail-form.tsx:1179` 無條件渲染 dialog，關閉時連元件都不 unmount。
**修法**：`fetchSSE` 增加 AbortSignal 參數，dialog 在 `onOpenChange(false)` 與 unmount cleanup 時 abort 兩條串流。｜CONFIRMED（反駁者建議降 LOW）

### M38. Playground 輸入框 Enter 未排除 IME 組字狀態，中文選字誤送半成品訊息
`apps/frontend/src/features/bot/components/playground-compare-dialog.tsx:229` ｜ correctness ｜ frontend-new-pages
**情境**：繁中使用者（本產品主要族群）用注音 IME 按 Enter 確認候選字 → `key==="Enter"` 且 `isComposing===true` → `preventDefault()` + `handleSend()` → 把組字中的不完整文字同時發給兩版影子對話 → 每次誤送消耗約 2 次 LLM 呼叫並**汙染兩欄 history_override**（後續輪次都帶著錯誤訊息）。
**證據**：全前端 grep `isComposing` 為 0 筆。此為 codebase 既有模式（`chat-input.tsx:23-26`、`bot-studio-canvas.tsx:575-578` 同寫法），本頁差別在誤送成本較高。
**修法**：Enter 分支前加 `if (e.nativeEvent.isComposing) return;`（建議三處一起修）。｜CONFIRMED

### M39. `useStudioStreaming` 的 `slowMode` 完全無效：handleEvent 未串行化
`apps/frontend/src/features/bot/hooks/use-studio-streaming.ts:124` ｜ correctness ｜ frontend-new-pages
**情境**：以 `slowMode: true` 送訊息（客戶 demo 慢速回放）→ `fetchSSE` 在同一 chunk 內同步連續呼叫 `onEvent`，wrapper 是 `void handleEvent(event)` 不 await；`handleEvent` 內所有 callbacks 都在第一個 await 之前同步執行，`if (slowMode) await sleep(800)` 排在**函式最後且之後沒有任何程式碼** → sleep 的 resolve 不影響任何可觀察行為 → 所有節點瞬間全亮，與不開 slowMode 完全相同。
**證據**：`slowMode` 不是死參數——`bot-studio-canvas.tsx:88/559/352` 有使用者可切的 checkbox，是使用者可見的 demo 功能且完全失效；:48 註解仍寫「每事件處理完 await 800ms」。
**修法**：改為事件佇列串行消費（push 進 queue，單一 async loop 逐一處理並 sleep），或讓 `fetchSSE` 支援 await onEvent。｜CONFIRMED

### M40. publish/rollback 版本後未 invalidate `bots.detail` → Bot 表單顯示舊值，儲存會覆寫剛發布的設定
`apps/frontend/src/hooks/queries/use-config-versions.ts:113` ｜ correctness ｜ frontend-hooks-types
**情境**：後端 publish 會把版本快照 `apply_snapshot` 套回 bot 本體並清 cache。前端 `useVersionMutation.onSuccess` 只 invalidate `configVersions.list` → 使用者發布 v5（改了 base_prompt）→ 60 秒內切到 bot-detail 頁（`staleTime` 60s 直接吃快取）→ 表單顯示發布前的 prompt → 使用者以為沒生效而按儲存 → **PUT 舊值回去，剛發布的設定被靜默還原**，且 `update_bot_use_case` 又記一個新版本。
**修法**：publish/rollback 的 onSuccess 額外 invalidate `queryKeys.bots.detail(botId)` 與 `bots.all(tenantId)`。｜CONFIRMED

### M41. `useRollbackRun`（optimizer 套用/回滾）只 invalidate runs → 版本時間線與 bot 設定全部 stale
`apps/frontend/src/hooks/queries/use-prompt-optimizer.ts:334` ｜ correctness ｜ frontend-hooks-types
**情境**：Phase D 後 optimizer rollback 已收斂到版本狀態機（`_rollback_via_version` 建 config version 並嘗試發布）。前端 onSuccess 只 invalidate `promptOptimizer.runs` → 使用者在 run 詳情頁按「套用此迭代」成功 → 60 秒內開版本時間線看不到新版本、開 bot-detail 看到舊 prompt → 同樣存在儲存舊表單覆寫新 prompt 的風險。
**證據**：`RollbackResult` 型別自己就帶 `version_id`/`published`，證明前端已知此操作會產生版本；兩個呼叫端頁面都沒有補 invalidate。
**修法**：onSuccess 依回傳值 invalidate `configVersions.list(botId)` 與 `bots.detail(botId)`（與 M40 同批修）。｜CONFIRMED

### M42. `apiFetch` 401→refresh→retry 遞迴無次數上限 → 持續 401 時無限請求迴圈
`apps/frontend/src/lib/api-client.ts:62` ｜ correctness ｜ frontend-hooks-types
**情境**：任何「目標端點持續回 401 但 `/auth/refresh` 持續成功」的狀態 → 無限遞迴，每輪都真的打 refresh（`refreshPromise` 只去重併發，完成即設回 null）→ 該請求 Promise 永不 settle、UI 掛住、對後端形成請求風暴。**確定的觸發路徑**：`auth_router.py:186-190` change-password 在 tenant_access token（無 user_id）時回 401，而 refresh 端點接受 `tenant_refresh` 並重新簽發同型別 token → 重試必然再 401；`App.tsx:123-126` 的 `/change-password` 路由對任何已登入者可直接以 URL 進入。另 L20 的登入情境（localStorage 仍留有可用 refreshToken 時打錯密碼）也會走出實際迴圈。
**修法**：加內部參數（如 `_retried: boolean`）限制 401 後最多重試一次，第二次直接走登出/拋錯路徑。｜CONFIRMED

### M43. 登出/換帳號不清 TanStack Query 快取 → 無租戶 discriminator 的 key 把前一租戶資料端給下一個登入者
`apps/frontend/src/stores/use-auth-store.ts:53` ｜ security ｜ frontend-hooks-types
**情境**：同一瀏覽器分頁（SPA 不 reload）：租戶 A 登出 → 租戶 B 登入 → 掛載 key 不含 tenant 的查詢（`["prompt-optimizer","datasets"]`、`["system-prompts"]`、`["provider-settings"]`、`["logs",...]`、`["observability",...]`）**直接命中租戶 A 的快取立即顯示**，且 60s staleTime 內連背景 refetch 都不發生。
**證據**：`logout` 只重設 store 欄位；全 src grep `queryClient.clear|removeQueries|resetQueries` 無結果；`providers.tsx` 的 QueryClient 以 useState 建於 root、跨登入登出存活；預設 gcTime 5 分鐘。對照 `bots`/`conversations` 的 key 有帶 tenantId，證明是遺漏。
**修法**：登出（含 apiFetch 401 強制登出）時呼叫 `queryClient.clear()`，或所有 queryKey 一律加入 tenantId 維度。｜CONFIRMED ｜ **可利用：是（本機情境）**（顧問/代理商同分頁切帳號、共用工作站、kiosk；無法遠端觸發，可利用性評估者建議降 LOW）

### M44. SSE 串流未收到 `done` 事件即結束時，`isStreaming` 永久卡 true
`apps/frontend/src/features/chat/hooks/use-streaming.ts:205` ｜ correctness ｜ frontend-hooks-types
**情境**：伺服器端乾淨關閉串流但沒送 `done`（generator 提前 return、反向代理正常結束 response）→ `fetchSSE` 正常 resolve（不走 onError、不 throw）→ `sendMessage` 的 try 之後沒有任何後續程式碼、catch 不會進 → `setIsStreaming(false)` 永不被呼叫 → **聊天輸入框永久鎖定，需整頁重載**。
**證據**：`setIsStreaming(false)` 只出現在 done handler、onError、catch 三處，成功路徑無 finally。
**修法**：把 `setIsStreaming(false)` / `setToolHint(null)` / `clearTimeout` 移到 finally 統一清理。｜CONFIRMED（兩名反駁者查遍後端所有出口皆保證 yield done，實際觸發需依賴代理層行為，建議降 LOW；屬防禦性缺失）

### M45. Studio `eventLog` 滿 80 筆後停止收事件 → 即時 DAG／時序軸在長回答中途凍結
`apps/frontend/src/features/bot/components/bot-studio-canvas.tsx:222` ｜ correctness ｜ frontend-existing
**情境**：Studio 試運轉一則較長回答：`onEvent` 對**每一筆** SSE event（含每個 token）呼叫 `setEventLog`，updater 為 `prev.length >= 80 ? prev : [...prev, event]`（硬上限、非環形）→ log 在前 ~80 筆 token 就滿 → 之後抵達的 `tool_calls` / `sources` / `worker_routing` / `error` 全部丟棄 → **ExecutionTimeline 與 LiveTraceGraph 中途凍結**，第二個以後的 tool 節點、RAG chunk、錯誤標記永遠不出現。
**證據**：`execution-timeline.tsx:56` 渲染時濾掉 token，但 token 仍佔滿 log 名額——正好坐實此論點。BlueprintCanvas 走專用 callback 不受影響，凍結範圍限於兩塊面板；supervisor/meta_supervisor 路徑一次 yield 整包答案，不會踩到。
**修法**：token event 不進 eventLog（只餵 `appendAssistantContent`），或滿了改成環形丟最舊；至少對非 token 的結構性事件不受上限限制。｜CONFIRMED

### M46. 最末頁刪光文件後 page 不回夾 → 使用者被困在空的幽靈頁且分頁控制自行隱藏
`apps/frontend/src/hooks/use-pagination.ts:8` ｜ correctness ｜ frontend-existing
**情境**：知識庫有 2 頁，使用者在 page=2 刪光該頁文件 → 後端回 `items=[]`、`total_pages=1`（後端不夾回超界 page）→ `usePagination` 無 clamp，page 停在 2 → DocumentList 顯示「尚未上傳任何文件。」（實際 page 1 還有）→ 同時 `PaginationControls` 因 `totalPages <= 1` return null **整個消失** → 使用者無任何 UI 可回到 page 1，只能重新整理或離開頁面。
**修法**：使用端加 `useEffect(() => { if (data && page > data.total_pages) setPage(Math.max(1, data.total_pages)); })`，或讓 `usePagination` 接受 totalPages 自動夾回。｜CONFIRMED

### M47. `DocumentList` 勾選狀態不隨 documents 變動修剪 → 全選判斷與批量計數錯誤
`apps/frontend/src/features/knowledge/components/document-list.tsx:486` ｜ correctness ｜ frontend-existing
**情境**：(A) page 2 全選 20 筆後返回**已快取的** page 1 → selectedIds 殘留 page 2 的 20 個 id → `allSelected = documents.length > 0 && selectedIds.size === documents.length` 為 true（只比 size 不比內容）→ 表頭全選誤顯示已勾，且點「批量刪除 (20)」**實際刪的是畫面上看不到的另一頁文件**（真實資料刪除，連帶移除向量資料）。(B) 勾選 doc A 後用單筆刪除刪掉 A → selectedIds 殘留 A，工具列仍顯示「已選 1 個」，批量刪除對已刪 id 送 API。
**證據**：全檔 `setSelectedIds` 只在 toggle/批量操作時變更，無任何依 documents 的 useEffect；`knowledge-detail.tsx:112` 未加 `key={page}` 故切頁不 remount。（校準：首次切到未快取頁時 data 變 undefined 使元件卸載、state 重置，故情境 A 的觸發方向應為「返回已快取頁」。）
**修法**：`allSelected` 改為 `documents.every((d) => selectedIds.has(d.id))`，並在 documents 變動時把 selectedIds 與現存 id 取交集（或切頁時清空）。｜CONFIRMED（原始 finder 建議可**上修**——後果是誤刪真實資料）

### M48. 孤兒清理測試測的是 mock 自己實作的行為，生產 SQL 零覆蓋
`apps/backend/tests/unit/prompt_gate/test_gate_run_lifecycle_steps.py:323` ｜ test-quality ｜ test-quality
**情境**：`CleanupOrphanGateRunsUseCase.execute()` 只是兩行委派。測試的 `_mark_orphans` side_effect **自己執行** `run.mark_error()`、`_revert` 自己把 version.status 改成 draft，Then 步驟斷言的正是 mock 剛設定的值 → 真正做事的 `mark_orphans_error` / `revert_validating_to_draft` 的 SQL 全 repo 無任何測試。若 WHERE 條件寫錯（漏掉 queued、或誤傷非孤兒 run），重啟後版本永久卡 validating，測試仍全綠。
**修法**：為兩個 repository 方法補 integration 測試（真實 DB），unit 層只留「execute 呼叫兩個方法且順序正確」。｜CONFIRMED（目前 SQL 本身正確，屬純測試缺口）

### M49. 「trace 未被持久化」scenario 在持久化不可能發生的配置下驗證
`apps/backend/tests/unit/prompt_gate/test_shadow_execution_steps.py:221` ｜ test-quality ｜ test-quality
**情境**：use case 以 `trace_session_factory=None` 建構，DB 寫入路徑根本不存在——無論生產程式的 `persist=not command.test_mode`（三處）被改成 `persist=True` 還是刪掉，這個 scenario 都不會失敗。實際只驗了 ContextVar 清空，**feature 宣稱的「trace 不落庫」隔離面沒有被真正防守**。
**證據**：`_persist_agent_trace` 在 factory 為 None 時有第二道早退，且整個函式體包在 `try/except Exception`；測試自己的註解承認「沒有任何 DB 寫入路徑」。
**修法**：注入 MagicMock trace_session_factory，斷言 test_mode 下 factory 從未被呼叫、non-test_mode 下被呼叫。｜CONFIRMED

### M50. 「conversation repository 未被查詢歷史」斷言 vacuous——command 未帶 `conversation_id`
`apps/backend/tests/unit/prompt_gate/test_shadow_execution_steps.py:240` ｜ test-quality ｜ test-quality
**情境**：`_command` 從不設定 `conversation_id`，而生產程式只在 `if command.conversation_id:` 時才呼叫 `find_by_id` → `await_count == 0` 在**任何模式下（連 test_mode=False）**都成立。真正的隔離語意（test_mode + 帶 conversation_id 時忽略該 id、不讀既有對話）完全沒有測試。
**修法**：在 history_override scenario 的 command 加上 `conversation_id="conv-x"`，斷言 `find_by_id` 仍未被呼叫。｜CONFIRMED

### M51. 缺 gate run 重複啟動 / validating 版本非法轉移測試（409 路徑零覆蓋）
`apps/backend/src/application/prompt_gate/gate_run_use_cases.py:249` ｜ test-quality ｜ test-quality
**情境**：`version.mark_validating(run.id)` 是防止同版本併發跑兩個 gate run 的**唯一防線**，但 `gate_settings.feature` 所有 scenario 的版本都是 draft，validating/published 起點的路徑零測試；`version_state_machine.feature` 的非法轉移只測 published 的 publish/reject，未覆蓋 `publish(validating)` / `reject(validating)`。若 `_VALIDATABLE` / `_PUBLISHABLE` 被誤加 validating，同版本會產生兩個併發 run 互相覆寫，測試全綠。
**修法**：加「對 validating 中的版本再次啟動 gate run 被拒（409）」與「對 validating 版本執行發布/放棄被拒」兩個 scenario。｜CONFIRMED

### M52. gate run 背景執行的預算中止與 API 錯誤分支無測試
`apps/backend/src/application/prompt_gate/gate_run_use_cases.py:494` ｜ test-quality ｜ test-quality
**情境**：三條關鍵分支零覆蓋：(1) `if actual_cost > budget_usd: aborted = True; break`——測試 budget=10.0、單題成本 0.001，永不觸發；(2) `_run_single_case` 例外 → 空 ChatResult → `api_error` 硬斷言——FakeClient 從不拋錯；(3) Round 2+ 只跑 P0——測試只有一個 P0 case，無法區分是否誤把 P1 也重跑（成本翻倍）。
**證據**：`gate_verdict.feature:26` 的 budget_exceeded 測的是純 domain 的 `compute_verdict` 函式，不涵蓋 `_execute_background` 的中止行為。
**修法**：加三個 scenario：預算極小 → `details.aborted=true`；client 拋錯 → verdict fail；混合 P0/P1 兩題 repeats=2 → 斷言 chat 被呼叫 3 次而非 4 次。｜CONFIRMED

### M53. 前端 #54 新元件與 hooks 大面積無測試
`apps/frontend/src/pages/admin-prompt-optimizer-versions.tsx:1` ｜ test-quality ｜ test-quality
**情境**：零測試的包括 `use-config-versions.ts`（210 行，publish/reject/rollback/start-gate-run/replay 全部 mutation hooks）、版本時間線頁（523 行）、`replay-compare-report.tsx`（123）、`version-metrics-card.tsx`（70）、`prompt-diff.tsx`（113），以及 `api-endpoints.ts` 本身。例：publish mutation 的 endpoint path 打字錯誤，vitest 全綠，使用者按「發布」得到 404。`gate-run-report.test.tsx` 自身也漏測 aborted 預算中止橫幅、`excluded_platform_cases` 顯示與 unstable 徽章（fixture 全部固定為 false/[]）。
**證據**：e2e 的 `admin/prompt-gate.feature` 第 2 行自陳「steps 待 dev 環境重建後實作」，grep 不到任何 step 實作，不構成覆蓋。
**修法**：至少補版本時間線頁的 MSW integration 測試（載入列表、按發布打對 endpoint、閘門未過 409 顯示錯誤）與 replay-compare-report 渲染測試；gate-run-report 補 aborted/excluded/unstable 三個分支。｜CONFIRMED

---

## LOW

| # | 標題 | file:line | 分類 | finder | 摘要 / 修法 | 驗證 |
|---|------|-----------|------|--------|------------|------|
| L1 | publish / reject / metrics 端點未驗證 `version.bot_id` 與路徑 `bot_id` 一致 | `interfaces/api/bot_config_version_router.py:300` | quality | prompt-gate-core | 同租戶下以 bot A 的 URL publish bot B 的版本，實際發布的是 B 的版本並改寫 B 設定；URL 與作用對象脫鉤導致 audit/前端誤導，未來細粒度授權時成為繞過點。對照 `get_version:261-265` 有此檢查。**證據修正**：`validate` 與 `replay-compare` **已有**檢查（`gate_run_use_cases.py:209`、`replay_use_cases.py:134`），僅 publish/reject/metrics 缺。**修法**：三個端點加上與 `get_version` 相同的檢查。 | CONFIRMED（範圍修正）｜無跨租戶洩漏 |
| L2 | `subscribe_progress` 對已結束且事件已被消費的 run 永遠不終止 | `infrastructure/prompt_optimizer/run_manager.py:187` | correctness | prompt-gate-background | `while True` 只在收到終止事件時 return，從不檢查 `run.status`；`publish_progress` 滿載時 `get_nowait` 丟最舊事件（可能正是 completed）→ 新訂閱者每 30s keepalive 無限循環。另 `_runs` dict 無任何 pop/TTL，ActiveRun 常駐記憶體至重啟。**修法**：timeout 後檢查 `run.status ∈ terminal` 即補發終止事件並 return；completed run 設 TTL。 | CONFIRMED（client 斷線 → CancelledError 可終結；觸發此路徑的前端元件為已知死元件） |
| L3 | `UsageRepository.find_by_tenant` 讀取時遺漏 `run_id` / `config_version_id` 映射 | `infrastructure/db/repositories/usage_repository.py:76` | correctness | usage-attribution | save 有寫入（:51-52）但讀取建構式漏帶兩欄 → entity 恆為 None。目前唯一消費端 `get_tenant_summary` 恰好不用故無症狀，是顆定時錯資料雷。**修法**：read-path 建構補上兩欄。 | CONFIRMED |
| L4 | eval 標記方向性缺口：可將生產對話重分類為 eval 類逃 quota | `application/usage/usage_context.py:51` | security | usage-attribution | `_require_shadow_authorized` 只驗「shadow body ⇒ 需 eval 標記」，反向不驗：tenant_admin 以自寫 client 對普通對話帶 `X-Usage-Category: playground` → 若該租戶 `included_categories` 是明確清單且未含新 eval 分類，`sum_billable_tokens_in_cycle` 的 IN 過濾便不計此流量。**修法**：非 shadow 請求拒絕 eval 標記 header，或部署時對既有清單租戶自動 union 三個 eval 分類。 | CONFIRMED ｜**可利用：是（多重前置）**——預設 `included_categories=None`（全計入）；需 tenant_admin + 自製 client；quota 目前非硬閘門，後果僅計費準確性 |
| L5 | widget stream 例外路徑未標記/持久化 failed trace | `interfaces/api/widget_router.py:204` | correctness | agent-pipeline | except 分支只回 error/done，不像 `agent_router.py:316-332` 呼叫 `mark_current_failed` + `_persist_agent_trace` → widget 通路的失敗完全不出現在 `agent_execution_traces` / Studio 觀測頁，該輪 trace 直接丟失。**修法**：把 agent_router 的例外 trace 處理抽成共用 helper（channel parity）。 | CONFIRMED |
| L6 | widget 無 `X-Visitor-Id` 時 `identity_source` 為 None，trace source 被誤標成 web | `interfaces/api/widget_router.py:189` | correctness | agent-pipeline | `identity_source="widget" if visitor_id else None` → `source=command.identity_source or "web"` → 通路別統計把 widget 流量算進 web。**修法**：widget 端點固定 `identity_source="widget"`（visitor_id 有無只影響 memory 身份解析）；改動前須確認 `_resolve_and_load_memory` 仍以 visitor_id 為鍵。 | CONFIRMED（官方 widget client 一律送 header，觸發窄） |
| L7 | 每個 webhook 請求 new 一個 `httpx.AsyncClient` 且從不關閉 | `infrastructure/line/line_messaging_service.py:19` | quality | channel-parity | factory 每次 create 新實例、`__init__` 建 AsyncClient、全 codebase 無 `aclose()` → 每請求遺留未關閉 client/socket，靠 GC 非確定性回收。**修法**：共用 module 級 AsyncClient（token 走 per-request header），或 factory 快取 per-bot 實例。 | CONFIRMED（`container.py:2475` 的 Singleton 只給舊端點用，洩漏限於 multitenant 路徑） |
| L8 | 舊 LINE webhook 端點的 postback 以 `tenant_id=""` 落 Feedback | `interfaces/api/line_webhook_router.py:86` | correctness | channel-parity | 硬編空字串傳入 `handle_postback` → `Feedback(tenant_id="")` 落庫 → 該回饋在任何按租戶過濾的報表中消失。對照 multitenant 路徑傳 `bot.tenant_id`。**修法**：舊端點用 `default_tenant_id` 設定值。 | CONFIRMED（舊端點確實有註冊，兩端點同時生效） |
| L9 | LINE 路徑 guard 記錄缺歸因：`check_input` 不帶 `user_id`、`process_message` 不帶 `bot_id` | `application/line/handle_webhook_use_case.py:656` | quality | channel-parity | LINE 輸入攔截的 guard_logs 無 user_id（web 有 visitor_id）；輸出攔截因 `bot_id=""→None` 無 bot 歸因 → 安全事件調查時 LINE 的攔截記錄無法對回使用者/bot。**修法**：`check_input` 補 `user_id=event.user_id`；兩處 `process_message` 補 `bot_id=bot.id.value`。 | CONFIRMED |
| L10 | Bot 快取把 LINE channel secret / access token 明文 JSON 寫入 Redis | `application/line/handle_webhook_use_case.py:68` | security | channel-parity | `_bot_to_json` 用 `dataclasses.asdict(bot)` 全欄位序列化（含兩個憑證）後寫入 RedisCacheService（明文 setex，TTL 約 120s）。DB 明文為既有狀態（見 M23），此處的增量是把暴露面從 PG 擴大到 Redis（含 dump/replica）。**修法**：序列化前剔除兩個 credential 欄位，cache miss 該兩欄時回 DB 補讀。 | CONFIRMED ｜**可利用：否**——需先取得 VM 內網存取或 RDB dump，無任何 API 可讀 Redis；屬「後入侵放大」。註：`REDIS_URL_OVERRIDE` 為內網無密碼，一旦內網落地即一跳直取所有 bot 憑證 |
| L11 | `update_feedback_tags` 無租戶驗證 → 跨租戶回饋標籤注入 | `interfaces/api/feedback_router.py:276` | security | security-tenant-isolation | 端點取得 tenant 但未使用；`update_tags(feedback_id, tags)` 簽章無 tenant_id，repo 更新條件僅 `message_id`。**兩處事實修正**：(a) 實作是 `merged = list(dict.fromkeys(existing + tags))` 的**附加**而非覆寫，既有標籤不會遺失；(b) 查找鍵實際是 message_id 而非 feedback_id。**修法**：`update_tags` 加 tenant_id 參數，repo 更新條件加 tenant 綁定。 | CONFIRMED ｜**可利用：否**——需已從其他管道取得他租戶 message UUID（無枚舉面、無 oracle），成果僅污染式標籤附加 |
| L12 | `_run_optimization` 的 finally 引用可能未綁定的 `prompt_db` → UnboundLocalError | `application/eval_dataset/run_use_cases.py:568` | correctness | eval-dataset + session-lifecycle（同時發現） | `prompt_db = None` 宣告在 try **內**第 310 行，而 `history_client`/`api_client` 在 try 外；:235-309 之間任何例外（如 `a["type"]` KeyError、`RunHistoryClient(self._db_url)` 建構失敗、`PromptDBClient` ImportError）→ finally 的 `if prompt_db:` 拋 UnboundLocalError → 從 finally 冒出成為未處理的 task exception，並**遮蔽原始錯誤**。**修法**：把 `prompt_db = None` 移到 try 之前與其他兩者並列。 | CONFIRMED |
| L13 | budget（max API calls）不計多輪 warm-up 與 retry 呼叫 | `prompt_optimizer/runner.py:168` | correctness | optimizer-package | `use_history_override=False`（CLI 預設）且多輪 case 平均帶 3 句歷史 → 每 case 實際打 4 次 API，但 `total_api_calls` 每輪只 `+= total_cases`，retry 也不計 → budget=200 的 run 實際可打 800+ 次，成本控制失效。**修法**：`_eval_all` 內實際計數每次 chat 呼叫並回傳。 | CONFIRMED |
| L14 | finally 中用新的 `asyncio.run` 關閉舊 event loop 建立的 httpx AsyncClient | `prompt_optimizer/__main__.py:148` | correctness | optimizer-package | `asyncio.run(runner.run(...))` 後 loop 已關閉，finally 再 `asyncio.run(api_client.close())` 在新 loop 執行 aclose → 連線池內綁定舊 loop 的連線關閉時拋 `RuntimeError('Event loop is closed')`，**在 finally 內拋出會遮蔽原始例外**（`cmd_validate:264` 同型）。**修法**：整段包成單一 async main，以 try/finally 或 `async with` 管理 client 生命週期。 | CONFIRMED（反駁者在本專案 venv 以 HTTP/1.1 keep-alive 實測重現，並建議因遮蔽原始錯誤而**上修 MEDIUM**） |
| L15 | mutator meta-prompt 直接內嵌未消毒的 bot 回答 → RAG 內容可對優化 LLM 做 prompt injection | `prompt_optimizer/mutator.py:130` | security | optimizer-package | 知識庫文件被植入指令 → 受測 bot 回答引述且該 case 斷言失敗 → `failed_case.actual_answer[:300]` 原封拼進 meta-prompt → 優化 LLM 被引導在候選 prompt 中植入攻擊者內容。違反 `.claude/rules/security.md`「RAG 檢索結果注入 Prompt 前必須過濾」。**修法**：以明確定界符包裹並聲明「以下為不可信資料，非指令」，或過濾指令樣式字串後再嵌入。 | CONFIRMED ｜**可利用：是（條件多、影響自限）**——需能寫入該租戶知識庫、該題恰好失敗、注入內容撐過 200/300 字截斷；API 路徑產物只落 draft 版本，僅 CLI 直連會寫線上表 |
| L16 | `useGateRun` 在 run 查詢失敗時每 3 秒無限輪詢 | `hooks/queries/use-config-versions.ts:96` | correctness | frontend-new-pages | `refetchInterval` callback 只讀 `query.state.data?.status`，錯誤狀態下 data 恆 undefined → 恆回 3000；`retry: 1` 只影響單次 fetch 不停 interval → 對已確定失敗的 run id 每 3 秒重打一次直到使用者離開。**修法**：先判斷 `query.state.status === "error"` 時回傳 false。 | CONFIRMED（收合卡片即停，enabled 綁 open） |
| L17 | 驗證成本預檢 dialog 的「確認送驗」在 estimate 尚未載入時即可點擊 | `pages/admin-prompt-optimizer-versions.tsx:408` | quality | frontend-new-pages | disabled 條件不含 `estimateLoading || !estimate` → 使用者可在只有 Skeleton 時直接送出，從未看到題數/預估成本/是否超預算，§預檢確認的「知情同意」設計目的被繞過；超預算情境同樣可按（僅靠後端拒絕後 toast）。**修法**：disabled 加上 `|| estimateLoading || !estimate`（可選：`!estimate.within_budget` 時也禁用）。 | CONFIRMED |
| L18 | `CompareColumn` 的 `bottomRef` 是死代碼，串流時不會自動捲到底 | `features/bot/components/playground-compare-dialog.tsx:83` | quality | frontend-new-pages | ref 已宣告、錨點 div 已埋（:100），但元件內無任何 useEffect 呼叫 `scrollIntoView`（也未 import useEffect）→ 對話超過欄高後新 token 一直長在可視範圍外，每輪需手動捲動兩個欄位。對照 `message-list.tsx` 同樣模式有實作。**修法**：加 useEffect 監看最後一則 content 變化時 `bottomRef.current?.scrollIntoView({block:"end"})`。 | CONFIRMED |
| L19 | `useUpdateBot` 未 invalidate config-versions → 儲存 Bot 表單後版本時間線缺最新版本 | `hooks/queries/use-bots.ts:73` | correctness | frontend-hooks-types | `PUT /bots/{id}` 在後端會透過 `_record_config_version` 產生 `mark_published` 的新版本並 `set_current`，但 onSuccess 只 invalidate `bots.all` + `bots.detail` → 60 秒內版本時間線看不到新版本、`is_current` 標記停在舊版本；若據此執行回滾會以過期時間線做決策。**修法**：onSuccess 加 invalidate `configVersions.list(botId)`（與 M40/M41 同批修）。 | CONFIRMED（gate 啟用時 PUT 直接 raise 不產生版本，窗口更窄） |
| L20 | 登入密碼錯誤（401）誤觸 session 過期分支 | `lib/api-client.ts:64` | correctness | frontend-hooks-types | 登入頁輸入錯誤密碼 → `/auth/login` 回 401 → apiFetch 進 401 分支 → tryRefresh 失敗 → `toast.error("登入已過期，請重新登入")` + `logout()` → 登入表單自己的錯誤訊息旁同時彈出語意錯誤的 toast。後端已為 change-password 特意改回 400 避開此坑（`auth_router.py:199-201` 註解自證），login 端點仍踩中。**修法**：apiFetch 對 auth.login/refresh 路徑跳過 401 分支，或僅在原請求帶有 token 時才視為 session 過期。 | CONFIRMED |
| L21 | `ChildrenRows` 固定渲染 7 個 td，但無 `onDelete` 時表格只有 6 欄 | `features/knowledge/components/document-list.tsx:336` | correctness | frontend-existing | admin 端 kb-studio `documents-tab.tsx:21` 不傳 onDelete → thead 與父列只 6 欄；展開 catalog 父文件後子列固定 7 個 td 且 loading 列 `colSpan={7}` → **多出一個沒有表頭的操作欄**（欄寬被擠壓，並出現 admin 端本不該有的「查看分塊/重新處理」按鈕）。**修法**：將欄數作為 prop 傳給 ChildrenRows，依 onDelete 決定 colSpan 與是否渲染最後一個 td。 | CONFIRMED（措辭修正：非既有欄位整體位移） |
| L22 | `openDocumentPreview` 建立的 blob URL 從未 revoke | `features/knowledge/components/document-list.tsx:117` | quality | frontend-existing | 每次 `URL.createObjectURL(blob)` 無對應 `revokeObjectURL`（全 repo grep 零結果）→ 整份文件（PDF/圖片可達數十 MB）在分頁存活期間佔住記憶體。**注意**：立即 revoke 會讓新分頁載入失敗，正確修法必須延時或在新視窗 load 後才 revoke。**修法**：新視窗 load 後或延時（如 60s）呼叫 `URL.revokeObjectURL(blobUrl)`。 | CONFIRMED（兩名反駁者建議進一步降為可選改善項） |

---

## 各 finder 覆蓋聲明

| Finder | 範圍摘要 | 讀檔數 | 原始/確認 | Coverage notes（重點） |
|--------|---------|-------|----------|----------------------|
| prompt-gate-core | 版本狀態機、config snapshot、static checks、版本 repository/router | 21 | 6 / 6 | 範圍內檔案全部完整讀畢（含 gate_run_entity、gate_run_repository、replay.py）。跨檔驗證檔（main.py、container.py、bot/entity.py、integration conftest）僅節選關鍵段落；gate_run/replay use cases 僅確認接口簽名。已知債未重報，但 C1 因後果比 journal 記錄的「交易縫隙」更嚴重且為確定性崩潰，故仍列出。 |
| prompt-gate-background | gate run / replay 背景執行、孤兒清理、run manager | 23 | 9 / 9 | 範圍內 7 檔全數完整讀畢。跨檔（container、main、send_message、routers、config、deploy yml、Makefile、Dockerfile）僅讀背景任務相關片段。未讀：`domain/prompt_gate/verdict.py` 內部邏輯、`assertions.py`、`eval_dataset/run_use_cases.py` 全文。`api_base_url` 問題同樣影響既有 optimizer/eval use cases，但僅以 gate/replay 角度回報。 |
| shadow-exec-isolation | test_mode 六面隔離、config_override / history_override 授權 | 18 | 6 / 6 | 範圍內 8 檔全數完整讀畢。跨檔：conversation_repository 只讀 100-180；query_rag_use_case 只讀 150-260（確認 tenant filter 強制，`config_override` 帶他租戶 kb_ids 不會洩漏向量資料）；gate/replay 只讀影子呼叫段；milvus_vector_store 與 run_use_cases 僅 grep。widget/LINE router 以 grep 確認無三個影子欄位。JWT role 無偽造路徑（deps.py 已完整讀）。 |
| usage-attribution | token 記帳、usage 分類、版本歸因、quota | 29 | 9 / 9 | 範圍內檔案全數讀完。跨檔為節選：send_message（840-870、1130-1266）、handle_webhook（960-1010）、eval_dataset/run_use_cases（290-400）、usage_router（前 120 行）；prompt_optimizer/api_client 僅 grep。quota/billing 只驗 `included_categories` 流向未深入審。前端 header 發送端未審（分區外）。 |
| agent-pipeline | 對話管線、guard、trace、widget/agent router 事件流 | 21 | 10 / 10 | 範圍內 8 檔全部完整讀畢。跨檔：container 只讀兩段 wiring；value_objects 只讀 TokenUsage；tools.py 只讀 invoke；query_rag/react_agent_service 以 grep 驗 tenant filter 與 sources 型別。已依噪音清單抑制 4 項。另兩個未報項：非 stream 路徑 guard 冗餘掃描（無錯誤結果）、`send_message_use_case.py:1143-1146` 的 `s if isinstance(s,dict) else s` no-op 死碼（修 widget 時可順手改）。 |
| channel-parity | LINE 通路與 web/widget 的功能對等 | 21 | 16 / 16 | 範圍內檔案全數讀完（含對照組 send_message_use_case 全 1587 行）。跨檔只讀必要片段：intent_classifier(160-320)、prompt_guard_service(前 120 + block_by_classifier)、agent_router(120-200)、replay_use_cases(100-220)、react_agent_service(695-734)、container webhook wiring。`domain/line/` 僅經呼叫端推斷未開檔。已知債依噪音抑制未重報；trace outcome 因屬「寫兩份」之外的具體 schema drift 後果而保留。LINE 獨有的 reasoning_effort 有註解明示為刻意 rollout，未列入。 |
| eval-dataset | eval dataset CRUD、optimizer run、validate/estimate | 22 | 12 / 12 | 跨檔只讀片段：container(2200-2330)、gate_run_use_cases `_collect_cases`(100-165)、session_middleware(前 80)、engine/deps/entity 以 grep 驗證。未深入 prompt_optimizer 獨立套件（屬其他分區）、run_manager 內部、eval_dataset ORM model。已知債（gate estimate 粗估、in-process create_task、_ShadowAPIClient duck-type）未回報。 |
| session-lifecycle | DB session 生命週期、背景任務、worker、middleware | 25 | 5 / 5 | container.py 全檔 2517 行完整讀畢；engine/session_middleware/atomic/main/worker/worker_resilience 全檔讀畢；三個背景任務檔全檔讀畢。跨檔僅讀 session 生命週期相關函式。全 src grep 確認 `BaseHTTPMiddleware` 為零（僅註解提及）；`get_tracked_session` 只有 container 一個掛載點。刻意略過 version_use_cases 主體與 gate create_task 弱引用（後者由 prompt-gate-background 回報）。 |
| security-injection | 注入面、加密、JWT、bot CRUD 授權 | 26 | 5 / 5 | 已完整讀過注入面核心檔。SQL 面：全後端 `text()`/f-string SQL 已 grep 掃過，`optimization_run_repository.py:78` 的 f-string 僅內插固定字面量，其餘皆參數化，**無 SQL injection**。Milvus filter 走白名單、query_rag 強制丟棄外來 tenant_id，向量檢索租戶隔離成立。#54 影子執行授權以 JWT role 判定，設計正確。未逐行讀完 gate/replay 背景任務主體（非注入面）。最嚴重發現（bot CRUD 缺租戶檢查）屬既有債而非 #54 新增，但確實可觸發故照報。 |
| security-tenant-isolation | 租戶隔離 / IDOR | 26 | 4 / 4 | 確認 #54 新路徑（config version / gate run / replay / estimate / metrics）的 tenant_id 一律取自 JWT 且以 id 直查者都走 tenant-scoped 或額外驗 bot 歸屬——**正確、無發現**。`find_recent_user_questions` 雙過濾正確；optimizer run 端點 `_scope()` + `_check_run_tenant` 正確。發現集中在既有 eval_dataset / feedback 端點的 IDOR（源自 558be1f，早於 #54），但 #54 讓平台通用集成為對話管線輸入，使 case CRUD 的缺檢查升級為跨租戶閘門汙染。未深追 `search_conv_summaries` 允許 tenant_id=None 的呼叫端全鏈。前端與測試檔未納入。 |
| optimizer-package | `apps/backend/prompt_optimizer/` 獨立套件 | 16 | 11 / 11 | 範圍內 12 個 .py 全數完整讀畢。`datasets/*.yaml` 只抽查 `target_prompt` 欄位；`_schema.json` 未讀。範圍外檔案僅讀呼叫相關區段——其中 3 項 findings（default_assertions 漏合併 ×2、validate 忽略 history）落在這些檔案，可能與該分區 finder 重複。已知問題（_ShadowAPIClient duck-type、PairwiseJudge 綁 OpenAI、gate estimate 粗估、mutator 綁 ChatOpenAI）未重報。 |
| frontend-new-pages | #54 新頁面與元件 | 19 | 7 / 7 | 範圍內 10 檔全部完整讀畢。跨檔驗證了 fetchSSE/apiFetch、API endpoint/query key 定義、Bot 型別 gate 欄位、後端影子授權（`_EVAL_USAGE_CATEGORIES` 含 playground、CORS `allow_headers=*`、header 路徑通）與 metrics 序列化（無 Decimal 字串風險）。bot-detail-form 與 agent-trace-graph 只讀呼叫關係相關片段。已知問題（run-progress 死元件、C901 債）未重報；replay 執行中顯示 gate 文案屬純文案問題未列入。 |
| frontend-hooks-types | 前端 hooks、快取失效、型別、API client | 24 | 9 / 8 | （coverage_notes 未提供）1 項被對抗性驗證剔除（見已知噪音）。 |
| frontend-existing | 既有前端頁面與元件 | 16 | 6 / 6 | 範圍內 10 檔全數完整讀畢。跨檔為節選：query_rag(85-124)、_query_rewriter(55-115)、llm_caller(1-115)、use-studio-streaming(前 120)、use-provider-settings(前 100)。另掃描三個測試檔以判斷 9 個紅測性質——結論：pagination 紅測為 aria-label 中英不符、document-list 紅測為元件改去副檔名顯示後斷言過期、provider-list 疑似 PROVIDER_ORDER 變動，**皆為測試過期而非元件 bug**，未另立 finding。provider-list model toggle 併發疑慮因有 optimistic update 已緩解，不成案。protected-route 僅 client-side 判斷、後端另有 enforcement，未列為漏洞。 |
| test-quality | 測試品質與覆蓋缺口 | 31 | 8 / 8 | send_message_use_case（1400+ 行）與 bot_config_version_router 只讀 #54 相關段落（grep 定位 + 節錄）。前端無測試的 #54 元件只確認測試缺席與行數，未逐行審內容。四個 feature 檔未讀原文（step definitions 已完整讀過，scenario 對映可從 step 推得）。E2E（playwright）層未掃描。 |

---

## 未覆蓋檔案清單

**620 / 788 檔（78.7%）未被任何 finder 讀過。** 以下依目錄分組。

> **下一輪 review 建議優先序**：① `interfaces/api/`（30 檔 router，含完全未審的 `auth_router.py`——多份 exploit_notes 指出其 `/register` 可匿名指定 role、`/token` 可匿名簽發任意 tenant_id，是本次多項 CRITICAL 的可達性放大器）② `application/knowledge/`（29 檔，知識庫 CRUD 是另一組租戶資源，極可能有與 C4~C9 同型的 IDOR）③ `infrastructure/db/repositories/`（27 檔，租戶過濾的實作面）④ `frontend/src/pages/`（47 檔）。

### 後端 — interfaces（31）
- `apps/backend/src/interfaces/api/`：admin_bot_router.py, admin_chunk_router.py, admin_conv_summary_router.py, admin_conversation_insights_router.py, admin_knowledge_base_router.py, admin_milvus_router.py, admin_outbox_router.py, admin_pricing_router.py, admin_router.py, admin_tools_router.py, **auth_router.py**, conversation_router.py, document_router.py, error_event_router.py, health_router.py, knowledge_base_router.py, log_router.py, mcp_router.py, mcp_server_router.py, notification_router.py, observability_router.py, plan_router.py, provider_setting_router.py, rag_router.py, rate_limit_middleware.py, security_router.py, system_prompt_router.py, task_router.py, tenant_router.py, worker_router.py
- `apps/backend/src/interfaces/api/schemas/`：pagination.py

### 後端 — application（127）
- `application/agent/`：list_built_in_tools_use_case.py, tool_label_resolver.py, update_built_in_tool_scope_use_case.py
- `application/auth/`：change_password_use_case.py, delete_user_use_case.py, get_user_use_case.py, list_users_use_case.py, login_use_case.py, register_user_use_case.py, reset_password_use_case.py, update_user_use_case.py
- `application/billing/`：_email_templates.py, get_billing_dashboard_use_case.py, list_quota_events_use_case.py, process_quota_alerts_use_case.py, quota_email_dispatch_use_case.py, topup_addon_use_case.py
- `application/bot/`：create_bot_use_case.py, delete_bot_use_case.py, list_all_bots_use_case.py, list_bots_use_case.py, upload_bot_icon_use_case.py, validate_bot_enabled_tools.py, worker_use_cases.py
- `application/chunk_category/`：assign_chunks_use_case.py, create_category_use_case.py, delete_category_use_case.py
- `application/conversation/`：data_retention_use_case.py, export_feedback_use_case.py, get_conversation_messages_use_case.py, get_conversation_token_usage_use_case.py, get_conversation_use_case.py, get_feedback_stats_use_case.py, get_retrieval_quality_use_case.py, get_satisfaction_trend_use_case.py, get_token_cost_stats_use_case.py, get_top_issues_use_case.py, list_conv_summaries_use_case.py, list_conversations_use_case.py, search_conversations_use_case.py, submit_feedback_use_case.py
- `application/health/`：health_check_use_case.py
- `application/knowledge/`：_admin_kb_check.py, _child_rename.py, _parent_aggregation.py, bulk_ingest_use_case.py, classify_kb_use_case.py, create_knowledge_base_use_case.py, delete_chunk_use_case.py, delete_document_use_case.py, delete_documents_by_source_use_case.py, delete_knowledge_base_use_case.py, extract_kb_dm_metadata_use_case.py, get_category_chunks_use_case.py, get_document_chunks_use_case.py, get_document_quality_stats_use_case.py, get_kb_quality_summary_use_case.py, get_processing_task_use_case.py, list_all_knowledge_bases_use_case.py, list_documents_use_case.py, list_kb_chunks_use_case.py, list_knowledge_bases_use_case.py, process_document_use_case.py, reembed_chunk_use_case.py, reprocess_document_use_case.py, split_pdf_use_case.py, test_retrieval_use_case.py, update_chunk_use_case.py, update_knowledge_base_use_case.py, upload_document_use_case.py, view_document_use_case.py
- `application/ledger/`：ensure_ledger_use_case.py, get_tenant_quota_use_case.py, list_all_tenants_quotas_use_case.py, process_monthly_reset_use_case.py
- `application/milvus/`：get_collection_stats_use_case.py, list_collections_use_case.py, rebuild_index_use_case.py
- `application/observability/`：agent_trace_queries.py, diagnostic_rules_use_cases.py, error_event_use_cases.py, notification_use_cases.py
- `application/outbox/`：admin_use_cases.py, drain_outbox_use_case.py, publish_outbox_event_use_case.py
- `application/plan/`：assign_plan_to_tenant_use_case.py, create_plan_use_case.py, delete_plan_use_case.py, get_plan_use_case.py, list_plans_use_case.py, update_plan_use_case.py
- `application/platform/`：create_provider_setting_use_case.py, delete_provider_setting_use_case.py, get_provider_setting_use_case.py, list_enabled_models_use_case.py, list_provider_settings_use_case.py, system_prompt_use_cases.py, test_provider_connection_use_case.py, update_provider_setting_use_case.py
- `application/platform/mcp/`：create_mcp_server_use_case.py, delete_mcp_server_use_case.py, discover_mcp_server_use_case.py, test_connection_use_case.py, update_mcp_server_use_case.py
- `application/pricing/`：create_pricing_use_case.py, deactivate_pricing_use_case.py, dry_run_recalculate_use_case.py, execute_recalculate_use_case.py, list_pricing_use_case.py, list_recalc_history_use_case.py
- `application/quota/`：compute_tenant_quota_use_case.py
- `application/rag/`：_hyde_generator.py, unified_search_use_case.py
- `application/ratelimit/`：get_rate_limits_use_case.py, seed_defaults_use_case.py, update_rate_limit_use_case.py
- `application/security/`：guard_rules_use_cases.py
- `application/tenant/`：create_tenant_use_case.py, get_tenant_use_case.py, list_tenants_use_case.py, update_tenant_use_case.py

### 後端 — domain（78）
- `domain/agent/`：built_in_tool.py, entity.py, services.py, team_supervisor.py, value_objects.py, worker.py
- `domain/auth/`：entity.py, password_service.py, repository.py
- `domain/billing/`：aggregates.py, email_sender.py, entity.py, quota_alert.py, repository.py
- `domain/bot/`：file_storage_service.py, repository.py, tool_rag_resolver.py, value_objects.py, worker_config.py, worker_repository.py
- `domain/conversation/`：entity.py, feedback_analysis_vo.py, feedback_entity.py, feedback_repository.py, feedback_value_objects.py, history_strategy.py, repository.py, summary_service.py, value_objects.py
- `domain/knowledge/`：entity.py, repository.py, services.py, value_objects.py
- `domain/ledger/`：entity.py, repository.py, topup_entity.py, topup_repository.py
- `domain/line/`：entity.py, services.py
- `domain/llm/`：prompt_block.py
- `domain/memory/`：entity.py, repository.py, services.py, value_objects.py
- `domain/observability/`：agent_trace.py, diagnostic.py, error_event.py, evaluation.py, log_retention_policy.py, notification.py, rule_config.py, trace_record.py
- `domain/outbox/`：entity.py, events.py, repository.py
- `domain/plan/`：entity.py, repository.py
- `domain/platform/`：model_registry.py, prompt_defaults.py, repository.py, services.py, value_objects.py
- `domain/pricing/`：entity.py, repository.py, value_objects.py
- `domain/rag/`：pricing.py, retrieval_mode.py, services.py, text_normalization.py
- `domain/ratelimit/`：entity.py, rate_limiter_service.py, repository.py, value_objects.py
- `domain/security/`：guard_config.py
- `domain/shared/`：cache_service.py, concurrency.py, constants.py, error_reporter.py, exceptions.py, pagination.py, pii_masking.py
- `domain/tenant/`：entity.py, repository.py, value_objects.py

### 後端 — infrastructure（123）
- `infrastructure/db/`：base.py, health_repository.py, seed.py
- `infrastructure/db/models/`（39）：billing_transaction_model.py, bot_knowledge_base_model.py, bot_worker_model.py, built_in_tool_model.py, chunk_category_model.py, chunk_model.py, conversation_model.py, diagnostic_rules_config_model.py, document_model.py, error_event_model.py, error_notification_log_model.py, eval_dataset_model.py, feedback_model.py, guard_log_model.py, guard_rules_config_model.py, knowledge_base_model.py, log_retention_policy_model.py, mcp_server_model.py, memory_fact_model.py, message_model.py, model_pricing_model.py, notification_channel_model.py, outbox_event_model.py, plan_model.py, processing_task_model.py, prompt_gate_run_model.py, prompt_opt_run_model.py, provider_setting_model.py, quota_alert_log_model.py, rag_eval_model.py, rate_limit_config_model.py, request_log_model.py, system_prompt_config_model.py, tenant_model.py, token_ledger_model.py, token_ledger_topup_model.py, user_model.py, visitor_identity_model.py, visitor_profile_model.py
- `infrastructure/db/repositories/`（27）：billing_transaction_repository.py, built_in_tool_repository.py, cached_guard_rules_config_repository.py, cached_worker_config_repository.py, chunk_category_repository.py, diagnostic_rules_config_repository.py, document_repository.py, error_event_repository.py, feedback_repository.py, guard_rules_config_repository.py, knowledge_base_repository.py, mcp_server_repository.py, memory_fact_repository.py, notification_channel_repository.py, outbox_event_repository.py, plan_repository.py, processing_task_repository.py, provider_setting_repository.py, quota_alert_log_repository.py, rate_limit_config_repository.py, system_prompt_config_repository.py, tenant_repository.py, token_ledger_repository.py, token_ledger_topup_repository.py, user_repository.py, visitor_profile_repository.py, worker_config_repository.py
- `infrastructure/auth/`：bcrypt_password_service.py
- `infrastructure/cache/`：in_memory_cache_service.py, redis_cache_service.py
- `infrastructure/classification/`：cluster_classification_service.py
- `infrastructure/concurrency/`：redis_conversation_lock.py
- `infrastructure/context/`：llm_chunk_context_service.py
- `infrastructure/conversation/`：full_history_strategy.py, llm_summary_service.py, rag_history_strategy.py, sliding_window_strategy.py, summary_recent_strategy.py
- `infrastructure/embedding/`：cached_embedding_service.py, dynamic_embedding_factory.py, fake_embedding_service.py, openai_embedding_service.py
- `infrastructure/file_parser/`：default_file_parser_service.py, ocr_file_parser_service.py, pdf_page_extractor.py, sliced_ocr_helper.py
- `infrastructure/file_parser/ocr_engines/`：base.py, claude_vision_ocr.py
- `infrastructure/langgraph/`：dm_image_query_tool.py, fake_agent_service.py, meta_supervisor_service.py, supervisor_agent_service.py, transfer_to_human_tool.py
- `infrastructure/langgraph/workers/`：fake_main_worker.py, fake_refund_worker.py
- `infrastructure/language_detection/`：langdetect_language_detection_service.py
- `infrastructure/llm/`：anthropic_llm_service.py, dynamic_llm_factory.py, fake_llm_service.py, llm_dm_metadata_extractor.py, openai_llm_service.py
- `infrastructure/logging/`：db_error_reporter.py, error_context.py, setup.py, trace.py
- `infrastructure/mcp/`：cached_tool_loader.py
- `infrastructure/memory/`：llm_memory_extraction_service.py
- `infrastructure/notification/`：email_sender.py, redis_throttle.py, sendgrid_quota_alert_sender.py
- `infrastructure/observability/`：rag_tracer.py, tool_trace_recorder.py
- `infrastructure/outbox/`：handlers.py
- `infrastructure/pricing/`：usage_recalc_adapter.py
- `infrastructure/queue/`：arq_pool.py
- `infrastructure/rag/`：llm_reranker.py
- `infrastructure/ratelimit/`：config_loader.py, redis_rate_limiter.py
- `infrastructure/storage/`：gcs_document_file_storage.py, local_document_file_storage.py, local_file_storage.py
- `infrastructure/text_splitter/`：content_aware_text_splitter_service.py, csv_row_text_splitter_service.py, json_record_text_splitter_service.py, recursive_text_splitter_service.py, separator_text_splitter_service.py

### 前端 — pages / routes（48）
- `apps/frontend/src/pages/`（47）：admin-billing.tsx, admin-bot-detail.tsx, admin-bots.tsx, admin-conversation-summary.tsx, admin-conversations.tsx, admin-diagnostic-rules.tsx, admin-error-events.tsx, admin-guard-rules.tsx, admin-kb-studio.tsx, admin-knowledge-bases.tsx, admin-log-retention.tsx, admin-logs.tsx, admin-mcp-registry.tsx, admin-milvus.tsx, admin-notification-channels.tsx, admin-observability.tsx, admin-outbox.tsx, admin-plans.tsx, admin-pricing.tsx, admin-prompt-optimizer-dataset-edit.tsx, admin-prompt-optimizer-dataset-new.tsx, admin-prompt-optimizer-datasets.tsx, admin-prompt-optimizer-run-detail.tsx, admin-prompt-optimizer-runs.tsx, admin-prompt-optimizer-start.tsx, admin-prompt-optimizer-validate.tsx, admin-prompt-optimizer.tsx, admin-prompts.tsx, admin-quota-events.tsx, admin-quota-overview.tsx, admin-rate-limits.tsx, admin-tenants.tsx, admin-token-usage.tsx, admin-tools.tsx, admin-users.tsx, bot-detail.tsx, bot-studio.tsx, bots.tsx, change-password.tsx, chat.tsx, feedback-browser.tsx, feedback-conversation.tsx, feedback.tsx, knowledge.tsx, quota.tsx, settings-providers.tsx, token-usage.tsx
- `apps/frontend/src/routes/`：paths.ts

### 前端 — hooks / stores / lib / types（65）
- `hooks/queries/`（33）：use-admin-quotas.ts, use-admin-tools.ts, use-admin-users.ts, use-admin.ts, use-agent-traces.ts, use-billing-dashboard.ts, use-built-in-tools.ts, use-categories.ts, use-conv-summaries.ts, use-conversation-insights.ts, use-conversation-search.ts, use-document-chunks.ts, use-document-quality-stats.ts, use-error-events.ts, use-feedback.ts, use-kb-chunks.ts, use-log-retention.ts, use-logs.ts, use-mcp-registry.ts, use-mcp.ts, use-milvus.ts, use-notification-channels.ts, use-observability.ts, use-outbox.ts, use-plans.ts, use-pricing.ts, use-quota-events.ts, use-rate-limits.ts, use-tasks.ts, use-tenant-quota.ts, use-tenants.ts, use-token-usage.ts, use-usage.ts
- `hooks/`：use-tenant-name-map.ts
- `lib/`：api-config.ts, chart-styles.ts, chart-tooltip-content.tsx, error-reporter.ts, format-currency.ts, format-date.ts, trace-id-format.ts, utils.ts
- `constants/`：streaming.ts, tool-labels.ts, usage-categories.ts
- `types/`（23）：agent-trace.ts, api.ts, auth.ts, bot.ts, chat.ts, chunk.ts, conv-summary.ts, conversation.ts, error-event.ts, feedback.ts, knowledge.ts, mcp-registry.ts, mcp.ts, milvus.ts, observability.ts, outbox.ts, plan.ts, platform.ts, pricing.ts, provider-setting.ts, token-usage.ts, user.ts, worker-config.ts

### 前端 — features / components（118）
- `features/admin/components/`（28）：add-mcp-server-dialog.tsx, admin-bot-filter.tsx, admin-tenant-filter.tsx, admin-tools-table.tsx, agent-trace-detail.tsx, agent-traces-filter-row.tsx, agent-traces-grouped-table.tsx, agent-traces-table.tsx, billing-by-plan-pie-chart.tsx, billing-revenue-line-chart.tsx, billing-top-tenants-table.tsx, conversation-search-result-card.tsx, create-tenant-dialog.tsx, diagnostic-rules-editor.tsx, mcp-registry-table.tsx, observability-evals-table.tsx, plan-form-dialog.tsx, pricing-create-dialog.tsx, pricing-history-table.tsx, pricing-recalc-wizard.tsx, request-logs-table.tsx, tenant-config-dialog.tsx, token-usage-bar-chart.tsx, token-usage-detail-table.tsx, token-usage-pie-chart.tsx, tool-scope-dialog.tsx, user-form-dialog.tsx, user-table.tsx
- `features/admin/components/prompt-optimizer/`：assertion-editor.tsx, cascade-mode-selector.tsx, index.ts, run-progress.tsx, score-chart.tsx
- `features/admin/conv-summary/`：conv-summary-list.tsx, conv-summary-search-panel.tsx
- `features/admin/conversation-insights/`：conversation-detail-panel.tsx, conversation-list-panel.tsx, conversation-messages-tab.tsx, conversation-summary-tab.tsx, conversation-token-usage-tab.tsx, conversation-trace-tab.tsx
- `features/admin/kb-studio/`：categories-tab.tsx, chunk-editor.tsx, documents-tab.tsx, kb-studio-tabs.tsx, quality-tab.tsx, retrieval-playground-tab.tsx, settings-tab.tsx
- `features/admin/lib/`：trace-layout.ts, trace-node-style.ts
- `features/admin/milvus/`：collection-table.tsx
- `features/auth/components/`：change-password-form.tsx, login-form.tsx, tenant-selector.tsx
- `features/bot/components/`：blueprint-canvas.tsx, bot-card.tsx, bot-list.tsx, create-bot-dialog.tsx, execution-timeline.tsx, mcp-bindings-section.tsx, tool-rag-config-section.tsx, workers-section.tsx
- `features/chat/components/`（12）：agent-thought-panel.tsx, bot-selector.tsx, chat-input.tsx, citation-card.tsx, citation-list.tsx, contact-card-button.tsx, conversation-item.tsx, conversation-list.tsx, feedback-buttons.tsx, source-image-gallery.tsx, tool-call-badge.tsx, tool-hint-indicator.tsx
- `features/feedback/components/`：bot-usage-summary-cards.tsx, conversation-replay.tsx, feedback-browser-table.tsx, feedback-stats-summary.tsx, satisfaction-trend-chart.tsx, tag-editor.tsx, token-period-selector.tsx, token-usage-section.tsx, top-issues-chart.tsx
- `features/knowledge/components/`：category-list.tsx, chunk-card.tsx, chunk-preview-panel.tsx, create-kb-dialog.tsx, knowledge-base-card.tsx, knowledge-base-list.tsx, quality-tooltip.tsx, reprocess-dialog.tsx, upload-dropzone.tsx, upload-progress-card.tsx, upload-progress.tsx
- `features/knowledge/hooks/`：use-categories.ts, use-category-chunks.ts
- `features/security/hooks/`：use-guard-rules.ts
- `features/settings/components/`：api-key-list.tsx, default-model-settings.tsx, provider-form-dialog.tsx, system-prompt-editor.tsx
- `features/usage/components/`：usage-bot-bar-chart.tsx, usage-bot-pie-chart.tsx, usage-daily-line-chart.tsx, usage-summary-cards.tsx
- `components/`：error-boundary.tsx
- `components/layout/`：app-shell.tsx, header.tsx, sidebar.tsx
- `components/shared/`：admin-empty-state-hint.tsx, model-select.tsx, page-breadcrumb.tsx
- `components/ui/`（26，shadcn 原生元件，風險最低）：alert-dialog.tsx, avatar.tsx, badge.tsx, breadcrumb.tsx, button.tsx, card.tsx, checkbox.tsx, circular-progress.tsx, collapsible.tsx, confirm-danger-dialog.tsx, dialog.tsx, dropdown-menu.tsx, input.tsx, label.tsx, progress.tsx, scroll-area.tsx, select.tsx, separator.tsx, skeleton.tsx, switch.tsx, table.tsx, tabs.tsx, textarea.tsx, toggle-group.tsx, toggle.tsx, tooltip.tsx
- 根層：`App.tsx`, `main.tsx`

---

## 已知噪音（對抗性驗證剔除項，供人工複核誤殺）

| finder | 標題 | file | 剔除理由 |
|--------|------|------|---------|
| frontend-hooks-types | `fetchSSE` 在 EOF 時丟棄殘留 buffer — 最後一個未以換行結尾的事件被靜默吞掉 | `apps/frontend/src/lib/sse-client.ts` | **兩名反駁者均成立**。失敗情境要求「一個完整事件停留在 buffer 而被丟棄」，但後端所有 SSE frame 都以 `\n\n` 結尾（全 repo grep `yield f"data` 僅 8 處，`agent_router.py:282/283/308/338/339` 與 `widget_router.py:202/207/208` 全部帶 `\n\n`），而 fetchSSE 的三個呼叫端打的都是這些端點。乾淨 EOF 時 `buffer = lines.pop()` 留下的必然是空字串；能殘留的只有被截斷的半個 frame，其 JSON.parse 本來就會失敗被 catch 略過，補上 flush 解析也救不回來。此外 chunked 串流被中途截斷時 `reader.read()` 會 reject（不會回 done=true），走 `use-streaming.ts:217-225` 的 onError 清理路徑，而非「靜默吞掉」。建議的 `decoder.decode()` flush 屬無行為差異的防禦性整理。 |

> **複核提示**：此項若未來後端新增不以 `\n\n` 結尾的 SSE 產出點（例如新通路 router 或自訂 heartbeat 格式），剔除前提即失效，屆時應重新評估。同時本次審查另有一批被 finder 主動判定為「非缺陷」而未提報的觀察，一併列出供複核：
> - 前端 9 個紅色測試（pagination-controls / document-list / provider-list）經查**皆為測試斷言過期而非元件 bug**（aria-label 中英不符、元件改為去副檔名顯示、PROVIDER_ORDER 變動）——需修測試而非修元件。
> - `send_message_use_case.py:1143-1146` 的 `s if isinstance(s, dict) else s` 為 no-op 死碼（sources 事件實證恆為 dict），修 widget 記帳時可順手改成 `to_dict` 保護。
> - 全後端 SQL 面已 grep 掃過：`optimization_run_repository.py:78` 的 f-string 僅內插固定字面量，其餘 `text()` 皆參數化綁定，**無 SQL injection**。
> - Milvus filter 走白名單、`query_rag_use_case` 強制丟棄外來 tenant_id key，向量檢索的租戶隔離**成立**；`config_override` 覆寫 `kb_ids` 亦被 tenant_id filter 擋住。
> - #54 新路徑（config version / gate run / replay / estimate / metrics）的 tenant_id 一律取自 JWT，以 id 直查的資源都走 tenant-scoped 查詢或額外驗 bot 歸屬——**這部分設計正確，無發現**。