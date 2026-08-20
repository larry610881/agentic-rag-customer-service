# 需求 Brief：Prompt 發布閘門 × Prompt 優化整合 × Eval Token 分流

> 給執行本需求的 Claude session：這是一份**需求書＋設計決策紀錄**，由另一個規劃 session 與 Larry 討論後定案。
> 你的任務分兩階段：**先產出規劃書（spec）與待決清單，經 Larry 確認後才開始開發。**
> 背景脈絡請先讀 `docs/observability-maturity-upgrade-plan.md` 的「第二項｜CI Eval 閘門」——本需求是其中「應用層閘門（P3）」的完整版，並擴充了功能開關與計費分流。

---

## 一、需求總覽（三件事，一起規劃）

1. **Prompt 發布閘門**：所有 bot prompt（存於 DB）的修改走 `draft → 驗證 → publish` 狀態機；驗證＝跑綁定的評測題集，通過判定才能發布。
2. **與既有 prompt 優化功能整合**：`prompt_optimizer` 套件（斷言引擎、dataset、run manager、rollback）與本閘門必須是**同一套子系統**，共用資料模型與執行機制，不得出現第二套平行實作。
3. **Eval token 用量分流**：閘門驗證與 prompt 優化消耗的 token，必須在用量帳中獨立分類、可歸因到租戶與 bot，並納入既有配額/計費/儀表板體系。

---

## 二、功能規格

### 2.1 功能開關（三層）

| 層級 | 控制者 | 行為 |
|------|------|------|
| 平台層 per-tenant | 平台管理者（admin） | 控制每個租戶是否**看得到／用得到**此功能 |
| Bot 層 mode | 租戶（在功能被開啟的前提下） | `off / warn / block`：warn＝驗證失敗仍可發布但顯示警告；block＝失敗即擋 |
| 啟用前置條件 | 系統強制 | **該 bot 未綁定任何評測題集時，閘門不可啟用**——UI 顯示「須先設定問題集」，狀態維持 off |

- **system 帳號（平台自有帳號）預設開啟**此功能，但同樣受「須先綁題集」前置條件約束。
- 沿用 `Bot.eval_depth`（`domain/bot/entity.py:102`）的既有模式新增設定欄位，不要另起一套 config 機制。

### 2.2 Prompt 版本化與狀態機

- 新增 prompt 版本表：每次修改 `bots.base_prompt`（含 UI 手動編輯——目前手動編輯**無任何歷史**，這是要順手補掉的洞）都產生一個版本列：`version_id, bot_id, prompt_snapshot, status(draft|published|rejected), author, created_at, gate_run_id(nullable)`。
- 線上永遠跑最新 `published` 版本；draft 不影響線上。
- 發布流程：
  1. **第 0 層同步靜態檢查**（毫秒級、免費）：模板變數齊全、長度上限、明顯 injection 句式 → 失敗直接擋，不跑 eval。
  2. 存為 draft。
  3. **非同步跑題集驗證**：沿用 `application/eval_dataset/run_use_cases.py` 與 `/validate` 既有機制（arq worker），不要重寫 runner。
  4. 判定通過 → publish（是否「通過即自動發布」vs「通過後人工按發布」＝待決點，見第五節）。
  5. 判定失敗 → 停在 draft，UI 顯示失敗案例明細；可修改重跑或放棄。
- Rollback：可一鍵回滾到任一歷史 published 版本（`prompt_opt_runs` 的 rollback 機制已有先例，對齊它）。

### 2.3 閘門判定規則（已定案，照此設計）

不是單一成功率，是分層判定：

```
通過 = 硬閘門通過率 100%
     AND 軟閘門通過率 ≥ 門檻（預設 80%，bot 級可調）
     AND 驗證成本 ≤ 預算上限
```

- **硬閘門**：資安與行為不變量斷言——`no_system_prompt_leak`、`no_role_switch`、`no_pii_leak`、`refused_gracefully`、`tool_was_called` 等（`prompt_optimizer/assertions.py` 現成）。錯一題即擋，warn 模式下也要醒目標紅。
- **軟閘門**：品質類斷言（contains、語言、長度、引用）。
- **抖動處理**：P0 案例用 N 次重跑取通過率（`validation_evaluator.py` 現成），預設 N=3 全過才算過。

### 2.4 題集（dataset）雙層設計

- **平台通用集**：平台維護、每個啟用閘門的 bot **強制注入**（沿用 `_security_base.yaml` auto-include 的既有設計思想），內容為跨領域不變量（資安、拒答行為、RAG 有查）。
- **Bot 自訂集**：租戶自填 golden Q&A，走既有 `eval_datasets` / `eval_test_cases` CRUD 與 YAML import（`interfaces/api/eval_dataset_router.py` 現成）。
- 「須先設定問題集」的判定 = 該 bot 綁定的自訂集至少有 1 個啟用案例（平台通用集不算數，避免空殼啟用）。

### 2.5 與 prompt_optimizer 的整合要求

- 優化器（Karpathy loop：run → LLM 改寫 → re-eval → accept）產出的新 prompt，**必須同樣走 2.2 的版本狀態機發布**——優化器接受的 prompt 也是一個 draft，過閘門才 publish。
- 共用：斷言引擎、dataset、run manager、`/estimate` 成本預檢、markdown report。
- Admin UI：現有 7 頁 prompt-optimizer 相關頁面與新的版本管理/閘門設定頁要整併規劃成一個連貫的「Prompt 管理」區，規劃書中須含資訊架構圖（哪些頁合併、哪些新增）。

### 2.6 Token 用量分流

- `domain/usage/category.py` 的 `UsageCategory` 新增分類——建議拆兩個：`eval_gate`（閘門驗證）與 `prompt_optimize`（優化迭代），是否合併為一個＝待決點。
- 寫入走既有 `application/usage/record_usage_use_case.py`（append-only 帳本），歸因欄位：tenant_id、bot_id、關聯 run_id。
- 計費策略 bot/tenant 級可設定：計入租戶配額 vs 平台吸收（預設＝待決點）。
- 防濫用：每 bot 每日驗證次數上限（可設定）；驗證前必跑 `/estimate` 成本預檢並顯示給操作者。
- 儀表板：`usage_router.py` 的 `/by-bot`、`/daily`、`/monthly` 與 `observability_router.py` 的 `/token-usage` 分組查詢須能呈現新分類（確認 group-by 是否自然支援，不行則補）。

---

## 三、既有零件對照（先讀這些，不要重造）

| 零件 | 位置 |
|------|------|
| 斷言引擎（32 種，含資安） | `apps/backend/prompt_optimizer/assertions.py` |
| Dataset schema / YAML / P0P1 | `apps/backend/prompt_optimizer/datasets/` + `migrations/add_eval_datasets.sql` |
| 驗證器（N 次重跑通過率） | `apps/backend/prompt_optimizer/validation_evaluator.py` |
| Run 管理 / rollback / report | `application/eval_dataset/run_use_cases.py`、`infrastructure/prompt_optimizer/run_manager.py` |
| API | `interfaces/api/eval_dataset_router.py`（含 `/eval`、`/estimate`、`/validate`）、`prompt_optimizer_run_router.py` |
| Bot 級 eval 設定先例 | `domain/bot/entity.py:102`（`eval_depth`） |
| 用量帳本 | `application/usage/record_usage_use_case.py`、`domain/usage/category.py`、`token_usage_records` |
| 配額/計費 | `token_ledgers`、`plans`、`quota_alert_logs`、`domain/rag/pricing.py` |
| 通知 | `application/observability/notification_use_cases.py` |

## 四、工程約束（repo 既有紀律，違反即打回）

- DDD 四層：domain 純淨、application 用例、infrastructure 實作、interfaces 路由。
- Migration 用手寫 SQL 檔（`apps/backend/migrations/`，無 Alembic），命名沿既有慣例。
- 自訂 middleware 一律 Pure ASGI，禁 `BaseHTTPMiddleware`。
- 觀測/記帳寫入 fail-open（fire-and-forget），不得影響主請求。
- 測試：pytest + pytest-bdd `.feature`，新用例比照既有覆蓋密度；閘門判定邏輯（分層規則）必須有完整單元測試。
- 多租戶隔離：所有新表帶 `tenant_id`，查詢走既有 scoping 模式。

## 五、待決清單（規劃書中逐項給建議方案，經 Larry 確認後才實作）

1. 通過後**自動發布 vs 人工確認發布**（建議：bot 級設定，預設人工）。
2. UsageCategory 拆 `eval_gate`/`prompt_optimize` 兩類 vs 合一類 `eval`。
3. 計費預設：租戶配額計入 vs 平台吸收。
4. v1 版本化範圍：只管 `bots.base_prompt`，還是連 `bot_prompt`/`worker_prompt`（supervisor/worker 模式）一起？（建議 v1 只做 base_prompt，留擴充點）
5. 「system 帳號」的精確定義：以什麼欄位/角色判定？
6. 平台通用集 v1 題目清單（領域判斷，需 Larry 參與定題）。
7. 軟閘門預設門檻 80% 與 N=3 重跑是否採納。

## 六、交付順序

**階段一（先做，產出後停下等確認）**：規劃書一份，含——資料模型變更（新表/欄位/migration 清單）、狀態機圖、API 端點增修表、UI 資訊架構、與 prompt_optimizer 的整合點圖、token 分流資料流圖、測試計畫、分 phase 的實作切分、第五節待決清單的建議方案。

**階段二（確認後）**：依規劃書分 phase 實作，每個 phase 附測試，migration 與 seed 齊備，最後更新 `docs/` 相關文件。
