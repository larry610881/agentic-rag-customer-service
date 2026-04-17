# 檔案系統破壞性操作安全規範

> 本 session（2026-04-17）的教訓固化：Claude 因「1」二義性誤解，對 8 個 session 起始就 untracked 的使用者本地檔案執行 `rm`（包含 `infra/schema.sql` / `dm-*-export.json` / `import-dm-to-cloud.py` 等）。這些檔案 git 沒追蹤 = 無法還原。使用者事後說「移除就算了，只是測試資料轉移」屬僥倖，不能當常態。

## 紅線（違反即 CRITICAL）

### 1. Untracked 檔案絕不擅自刪除 / 覆蓋

**Claude 對 `git status` 顯示為 `??` 的檔案不得執行：**
- `rm` / `rm -rf`
- `mv`（等同刪除原位置）
- `Write` tool 覆寫內容（`Write` 會覆蓋整檔，等同先刪再建）
- `truncate` / `> file`

**Untracked = 使用者本地 in-progress 工作**，可能是測試資料、備份、半成品腳本。即使它看起來「應該刪掉」也不可擅自動手。

### 2. 歧義解讀時寧可多問一次

當使用者給的指令有多種合理解讀（例如「1」、「第一個」、「那個檔案」），**必須列出你理解的候選 + 選一個當預設 + 等使用者確認**，不要直接動手執行破壞性動作。

範例錯誤做法：
```
User: 先幫我移除
Claude: [直接執行 rm]  ❌
```

範例正確做法：
```
User: 先幫我移除
Claude: 你是指 (A) item 1 的 X、(B) 整個 Y table、(C) 別的？
         我傾向 (A)，等你回覆再動手。
```

### 3. 允許的破壞性動作（例外白名單）

僅在以下情境可不經額外確認：
- 使用者**明確指定檔案路徑** + **明確動詞**（「刪除 apps/foo/bar.py」、「覆蓋 README.md 加上 X」）
- 動作目標為 git 追蹤中檔案，可由 `git restore` / `git reset` 還原
- 新建檔案（`Write` tool 寫到不存在的路徑）

## 必要的操作前檢查

執行 `rm` / `mv` / `Write` 覆寫前，**先 `git status --short` 檢查目標檔案狀態**：

| Status | 可否直接執行 |
|--------|-------------|
| `M` 已追蹤有修改 | ✅（git restore 可還原）|
| ` M` 工作區有修改 | ✅（git restore 可還原）|
| `A` 剛新增已 staged | ✅ |
| `??` untracked | ❌ 先問使用者 |
| `!!` ignored | ⚠️ 通常 OK 但若看起來是重要本地檔（如 `.env`）需先問 |

## 恢復路徑（若真的發生誤刪）

按以下順序嘗試：
1. `git log --all -- <file>`：如果曾經被 commit 過，可用 `git checkout <sha> -- <file>` 還原
2. VS Code Timeline：`Ctrl+Shift+P` → `Timeline: Focus on Timeline View`（開過該檔就有）
3. IDE 本地歷史（JetBrains: Local History；VS Code: Timeline）
4. 使用者自己的其他備份（Dropbox / iCloud / 外接碟）
5. 從可重建來源重新產生（例如 DB schema 可從 `pg_dump --schema-only`）

**Untracked 檔案無法從 git 恢復**，這是此規範存在的主因。

## 其他高風險操作（非本 rule 主題但提醒）

- `git reset --hard` / `git clean -fd` — 會清掉 working tree 修改與 untracked 檔
- `git push --force` — 影響遠端共享狀態（見 `git-workflow.md`）
- `DROP TABLE` / `DROP COLUMN` — 見 `migration-workflow.md`
- 批次修改超過 10 個檔的 replace_all / find-and-replace — 先確認 scope

這些動作 CLAUDE.md 與其他 rule 已有規範，此檔不重複。

## 可檢查項（Stop hook 未來可擴充）

- Session 內若有 `Bash(rm|mv)` 指令 且目標檔曾顯示為 `??`，自動 `ok: false`
- Write tool 覆蓋不在 git 追蹤內的檔案，先警告
