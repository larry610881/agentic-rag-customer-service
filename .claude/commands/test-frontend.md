# 執行前端測試

執行前端 Vitest 測試。可指定特定路徑或執行全套測試。

## 使用方式

- `/test-frontend` — 執行全部前端測試
- `/test-frontend src/features/chat/` — 執行指定目錄
- `/test-frontend --e2e` — 執行 E2E BDD 測試

## 執行步驟

1. 若 `$ARGUMENTS` 為空，執行全部 unit + integration 測試：

```bash
cd apps/frontend && npx vitest run --reporter=verbose 2>&1
```

2. 若 `$ARGUMENTS` 指定了路徑，執行指定範圍：

```bash
cd apps/frontend && npx vitest run $ARGUMENTS --reporter=verbose 2>&1
```

3. 若 `$ARGUMENTS` 包含 `--e2e`，執行 E2E BDD 測試：

```bash
cd apps/frontend && npx bddgen && npx playwright test --reporter=list 2>&1
```

4. 分析測試結果：
   - 若全部通過，輸出通過摘要
   - 若有失敗，列出失敗的測試案例與錯誤訊息，並提供修復建議

5. 若需要查看覆蓋率：

```bash
cd apps/frontend && npx vitest run --coverage 2>&1
```
