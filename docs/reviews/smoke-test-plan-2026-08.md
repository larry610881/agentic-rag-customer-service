# 新環境 Smoke Test 計畫（Full Review 修復後驗收）

> 對象：GCP 重佈署後的一次性全量驗收（驗完公開給業務）。
> 原則：**P0 先跑（環境沒起來其他免談）→ P1 是這波 review 行為變更的重點驗證
> → P2 是回歸掃尾**。每項都標對應 finding，出問題可直接回查
> `full-review-2026-08-20.md` 與 `full-review-2026-08-20-fixes.md`。

---

## P0 — 部署成功判定（~15 分鐘，任一失敗即停）

| # | 測什麼 | 步驟 | 預期 | 對應 |
|---|--------|------|------|------|
| P0-1 | 後端啟動 fail-fast | Cloud Run 部署後看啟動 log | 服務正常起來。若 log 出現「JWT_SECRET_KEY 仍為預設值」或「ENCRYPTION_MASTER_KEY 未設定」→ **這是設計行為**，去補 GitHub secrets 再重佈 | M24 |
| P0-2 | Health + DB | `GET /api/v1/health` | 200、database: connected | — |
| P0-3 | 孤兒清理啟動不誤殺 | 啟動 log 找 `gate_run.orphans_cleaned` | 有這行且 runs=0（全新 DB）；無 exception | M5/M7 |
| P0-4 | 前端載入 + 登入 | 開前端 → 登入 | 進得去、sidebar 正常 | — |
| P0-5 | Schema 完整性 | 上傳一份小文件到知識庫 | 文件進 pending → processed（worker 正常、Milvus 正常） | — |

## P1 — Review 行為變更重點（這波你「特別需要確認」的核心，~60-90 分鐘）

### A. 閘門版控主流程（改動最重的區域）

| # | 測什麼 | 步驟 | 預期 | 對應 |
|---|--------|------|------|------|
| A-1 | 建版→驗證→發布 happy path | Bot 設定改 base_prompt → 建版本 → 送驗 → gate run 跑完 → 發布 | 全程無 500；版本時間線狀態正確流轉 draft→validating→pending_publish→published | C1/H18 |
| A-2 | **連點防護** | 對同一 draft 版本快速連按兩次「送驗」 | 一次成功、一次 **409**（不是兩個 run 同跑、不是 500） | M6 |
| A-3 | **並發 publish/reject** | 版本 pending_publish 時，開兩個分頁分別按發布與放棄（盡量同時） | 只有一方成功，另一方 409；bots 設定與最終狀態一致 | M3 |
| A-4 | 版本卡死救援 | 送驗進行中 → **手動重佈/重啟 Cloud Run** → 等新實例起來 30 分鐘後（寬限窗）再看該版本 | run 標 error、版本退回 draft 可重驗（不會永卡 validating）。註：30 分內不清是 M7 寬限窗設計 | M4/M5/M7 |
| A-5 | 非管理員權限 | 用 role=user 的成員 token 打版本寫入端點 | 403（publish/reject/validate 需 tenant_admin） | H4 |
| A-6 | URL 歸屬一致性 | 以 bot A 的 URL publish bot B 的版本 id | 404 | L1 |
| A-7 | 回放對比標注 | 跑一次 replay-compare | 報告正常渲染；知悉其為 web 管線近似（details 有 pipeline_approximation） | M22 |
| A-8 | rollback 免驗直發 | 對已發布過的舊版本執行回滾（gate 開啟狀態下） | 直接發布成功，不被閘門擋 | H1 |

### B. 影子執行隔離（Playground）

| # | 測什麼 | 步驟 | 預期 | 對應 |
|---|--------|------|------|------|
| B-1 | Playground 不污染生產 | Playground 對照測試跑幾輪 → 看對話列表與 admin trace 觀測頁 | **沒有**多出對話、沒有影子 trace；token 用量標在 playground 分類非 chat_web | M8/M9/M14 |
| B-2 | Playground 中途出錯 | 對照測試時故意選會逾時/出錯的設定（或斷網重試） | 錯誤 trace 也不落生產表 | M8 |

### C. LINE 通路（客戶第一線）

| # | 測什麼 | 步驟 | 預期 | 對應 |
|---|--------|------|------|------|
| C-1 | **憑證遮罩 round-trip** | 輸入 LINE 憑證存檔 → 重新整理表單（顯示 `***`）→ **不動憑證欄位**改別的設定再存 → 用 LINE 發訊息 | LINE 正常回覆（證明 `***` 被當「不變更」、原憑證還在）。這是**最容易出事的一條**，務必測 | M23 |
| C-2 | 假簽章 | `curl -X POST .../api/v1/webhook/line/{short_code} -H 'X-Line-Signature: bad' -d '{}'` | **403**（不是 500）；LINE 官方 verify 按鈕也應通過 | M15 |
| C-3 | 不存在的 bot | 同上但 short_code 亂填 | 404 | M15 |
| C-4 | 正常對話 | 手機 LINE 問一題知識庫內問題 | 秒回 loading → 正常回答＋來源；後台 trace 有該輪、outcome 非 NULL | M15/M20 |
| C-5 | 群組事件 | 把 bot 拉進一個群組（或群組內發言） | 不炸（webhook 不 500）、1:1 訊息不受影響 | M18 |
| C-6 | postback 回饋 | 對回覆按 👍/👎 | feedback 落庫且帶正確 tenant | L8 |
| C-7 | 攻擊題 | LINE 發角色劫持題（家樂福事件同型） | 被擋，固定文案 | H11 對照 |

### D. 跨租戶 / 快取隔離

| # | 測什麼 | 步驟 | 預期 | 對應 |
|---|--------|------|------|------|
| D-1 | **同分頁換租戶** | 租戶 A 登入逛過 系統提示詞/Provider 設定/用量頁 → 登出 → **不重新整理** 直接登入租戶 B | 各頁面**不會閃現 A 的資料**（連一瞬間都不該有） | M43 |
| D-2 | 跨租戶 id 探測 | 用 A 的 token 打 B 的 conversation/dataset/bot id | 一律 404 | C2/C4-C9 |
| D-3 | 後門確認 | `POST /api/v1/agent/test-back`（或原後門路徑） | 404（已刪除） | M11 |

### E. Eval / Optimizer

| # | 測什麼 | 步驟 | 預期 | 對應 |
|---|--------|------|------|------|
| E-1 | 多輪題 validate | 用含多輪 case 的資料集（內建 security base 即有）跑 validate | 多輪題不再必掛（bot 有上下文回答） | M32 |
| E-2 | 預檢知情同意 | 開送驗確認 dialog | estimate 載入完成前「確認送驗」不可按；超預算也不可按 | L17 |
| E-3 | token 過期中斷 | （可選）長 validate 中途讓 token 過期 | 整輪 502 作廢，run 歷史**沒有**假 FAIL | M28 |

### F. 資源穩定性（你的 pool-leak 痛點）

| # | 測什麼 | 步驟 | 預期 | 對應 |
|---|--------|------|------|------|
| F-1 | **連線池體檢** | 上傳幾份文件 + 連續對話 10 輪 + 跑一次 gate run 後，對 DB 執行：`SELECT state, count(*) FROM pg_stat_activity WHERE datname='agentic_rag' GROUP BY state;` | **無累積的 `idle in transaction`**（短暫 1-2 個屬正常，數分鐘後應歸零） | M29/M30/H13/H14 |
| F-2 | 寫入後連打 | 連續 POST 類操作 10+ 次（建版/上傳/回饋） | API 不 hang（歷史上 pool 耗盡的典型症狀是 GET 正常 POST 掛） | 全域規範 |

## P2 — 回歸掃尾（~30 分鐘，抽測）

| # | 測什麼 | 預期 | 對應 |
|---|--------|------|------|
| G-1 | Widget：嵌入頁對話 + 串流 + 來源顯示 | 正常；trace source 標 widget 非 web | L5/L6 |
| G-2 | Studio 試運轉長回答 | DAG/時序軸**全程更新到結束**（不會中途凍結） | M45 |
| G-3 | 知識庫文件多頁勾選 | 換頁後全選狀態正確、批量刪除數字正確 | M46/M47 |
| G-4 | Bot 表單存檔後版本時間線 | 立即看到新版本（不用等 60 秒） | M40/L19 |
| G-5 | 登入打錯密碼 | 只有表單錯誤訊息，**不會**彈「登入已過期」toast | L20 |
| G-6 | 文件預覽 | 點預覽開新分頁正常（60 秒後 revoke 不影響已開啟的分頁） | L22 |
| G-7 | admin kb-studio 文件表格 | 展開子頁欄位對齊、無多餘操作欄 | L21 |
| G-8 | 用量頁 | chat/eval 分類分開呈現；quota 計算含 eval 分類 | #54/L4 |

---

## 已知不用測（明文延後/近似）

- **LINE 的長期記憶**：本來就沒接（channel-parity 債務 #6），memory_enabled 對 LINE 無效是已知狀態。
- **SSE 中途關分頁的 token 記帳**（M12）：極窄窗口，債務 #5 排期。
- **DB dump 層級的 LINE 憑證加密**（M23 at-rest）：需要 migration + 金鑰輪替，另案。

## 出問題時

1. 先對照 `full-review-2026-08-20-fixes.md` 的「部署注意事項」。
2. 判斷是「新環境設定問題」（secrets、schema、seed）還是「程式回歸」——
   P0 層失敗幾乎都是前者。
3. 回報時帶：哪一項編號、實際 vs 預期、後端 log 相關段落。
