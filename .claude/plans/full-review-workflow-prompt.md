# 全專案深度 Code Review — Workflow 執行指示（完整版）

> 用法：新 session 貼一句「讀 `.claude/plans/full-review-workflow-prompt.md` 並照做，用 workflow 跑全專案 review」即可。
> 本檔由 2026-08-20 的開發 session 準備，包含新 session 缺少的全部背景。

## 授權與規模聲明

- 我（Larry）**明確授權使用多代理 Workflow** 跑全專案深度審查（完整版）。
- 規模覆寫本 session 的 workflow 大小預設：**允許 30–45 個代理**（finder ~14 + 對抗性驗證 + 合成）。
- Token 預期 **6–9M**；純靜態讀碼——不跑程式、不需要 DB/API key、**絕不修改任何檔案、不 commit、不 push**。產出是報告。

## 專案背景（新 session 必讀）

- Monorepo：`apps/backend`（Python FastAPI + LangGraph，DDD 四層：domain/application/infrastructure/interfaces）+ `apps/frontend`（React/Vite/TS）+ `apps/backend/prompt_optimizer`（獨立套件）。生產碼約 10.5 萬行。
- **剛完成 Issue #54（已 closed）**：Prompt 發布閘門 × Bot 設定整包版控 × Eval Token 分流，A–G 七階段全在 main（`73416e8..HEAD` 約 20+ commits）。規格書 `docs/prompt-gate-spec.md`、計畫 `.claude/plans/prompt-gate-phase-c-plan.md`、學習筆記 `docs/architecture-journal.md`（最新 7 則都是本案）。
- 測試基線：後端 unit **1235 passed**；前端 **252 passed + 9 failed（既有債，見下方噪音清單）**。
- 審查紀律參考：`.claude/rules/`（python-standards、security、channel-parity、migration-workflow）。

## 審查目標（依價值排序）

1. **#54 新攻擊面與正確性**（最高優先）：
   - `config_override`/`test_mode`/`history_override` 影子執行：授權邊界（`agent_router._require_shadow_authorized` 403、`usage_context.resolve_usage_context` role 白名單）能否繞過？test_mode 六面隔離（對話/guard 攔截分支/memory/線上 eval/trace/usage）有無漏網寫入？
   - 版本狀態機與 publish 閘門分支（`application/prompt_gate/version_use_cases.py`）：非法轉移、race（同 bot 並發 publish/validate）、`is_current` 不變量。
   - 背景任務（gate run / replay / optimizer）：`independent_session_scope` + `.provider` factory 用法是否正確、例外路徑是否都會把版本從 validating 救回、asyncio.create_task 的異常吞沒。
   - Tenant scoping 全覆蓋：config-versions/gate-runs/replay/metrics/run 端點、以及 `find_recent_user_questions` 等新查詢。
   - Token 分流記帳正確性：header 標記、run_id/config_version_id 歸因、fail-open 方向。
2. **舊碼與交界**（本案最大盲區）：
   - `application/agent/send_message_use_case.py`：execute 與 execute_stream 複製分身（複雜度 25）——雙路不對稱 bug、#54 守衛是否兩路等價。
   - `application/line/handle_webhook_use_case.py`：LINE 獨立路徑與 web 路徑的 channel-parity（`.claude/rules/channel-parity.md` 紅線）。
   - `application/eval_dataset/eval_use_cases.py` 與 `run_use_cases.py`：重複區塊、`/validate` 同步阻塞、背景任務生命週期。
   - `container.py`（2000+ 行）：session 生命週期紅線（singleton 持 session、急切 resolve）。
3. **前端**：新頁面（admin-prompt-optimizer-versions、playground-compare-dialog、gate-run-report/replay-compare-report）的狀態管理與競態（雙 stream 並發 setState）、`as any`/型別逃逸、a11y；9 個紅測背後的元件。
4. **資安橫切**：SQL injection（text() 拼接）、prompt injection 面（history_override 是新輸入面）、秘密處理（mcp_bindings env_values、LINE credentials）、CORS/認證完整性。

## 已知問題清單（噪音抑制——除非發現「更深層」問題，否則不要重複回報）

- 前端 9 個既有失敗測試：pagination-controls ×4、document-list ×2(含 integration)、provider-list ×3——已知債，另開卡處理中。
- 原始 `npx tsc --noEmit` 有雜訊（專案 gate 是 eslint+vitest+vite build）：bot-detail-form 的 zodResolver/Control TS2322/2719、測試檔缺 vitest globals——HEAD 既有。
- mypy 既有錯誤：`update_bot_use_case.py` 8 個（`_UNSET` object 型別戲法）、`run_use_cases.py` 2 個。
- C901 複雜度既有債：`_load_bot_config`(26)、`_execute_stream_inner`(25)、`_run_optimization`(18)、`_apply_updates`(25)、`worker_use_cases.execute`(15)——「太複雜」本身不用報，但**裡面藏的實際 bug 要報**。
- journal 已記錄的已知風險（不用重報，除非能證明後果比記錄的嚴重）：publish 跨表非同交易縫隙、PairwiseJudge 綁 OpenAI 型 client、gate estimate 粗估、gate run in-process create_task 重啟中斷、`_ShadowAPIClient` duck-type、快照白名單與實體欄位靠守衛測試同步。
- `run-progress.tsx` 的 EventSource URL 缺 /v1 且無 token（已知死元件）；`useCreateTestCase` 舊 shape + `as never`（既有）。

## Workflow 結構要求

- **Phase Find**：~14 個 finder，分區 × 維度（後端各 bounded context ×正確性、資安專審 ×2〔injection 面/租戶隔離〕、session 生命週期專審、channel-parity 專審、optimizer 套件、前端 ×3〔新頁面/hooks 與型別/既有元件〕、測試品質 ×1〔斷言強度、mock 是否測到真行為〕）。每個 finder 給明確檔案範圍與「已知問題清單」。
- **Phase Verify（完整版）**：**每個 finding** 交 2 個獨立反駁者（prompted to REFUTE，讀原始碼定點查證），≥1 反駁成立即降級或剔除；對資安類 finding 用第 3 個「可利用性」視角。
- **Phase Synthesize**：去重（by file+root cause）、分級（CRITICAL/HIGH/MEDIUM/LOW）、每項含 file:line、失敗情境（具體輸入→錯誤結果）、建議修法一句話。
- **產出**：寫入 `docs/reviews/full-review-2026-08-20.md`（分級排序 + 統計摘要 + 各 finder 覆蓋聲明——哪些檔沒被任何 finder 讀到要列出）。**不修任何程式碼**。
- 完成後在對話中給我 CRITICAL/HIGH 的摘要與建議修復順序。
