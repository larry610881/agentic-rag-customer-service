# 執行後端測試

執行後端 pytest 測試。可指定特定路徑或執行全套測試。

## 使用方式

- `/test-backend` — 執行全部後端測試
- `/test-backend tests/unit/knowledge/` — 執行指定目錄
- `/test-backend tests/unit/knowledge/test_query_steps.py` — 執行指定檔案

## 執行步驟

1. 若 `$ARGUMENTS` 為空，執行全部測試：

```bash
cd apps/backend && uv run python -m pytest tests/ -v --tb=short 2>&1
```

2. 若 `$ARGUMENTS` 指定了路徑，執行指定範圍：

```bash
cd apps/backend && uv run python -m pytest $ARGUMENTS -v --tb=short 2>&1
```

3. 分析測試結果：
   - 若全部通過，輸出通過摘要
   - 若有失敗，列出失敗的測試案例與錯誤訊息，並提供修復建議

4. 若需要查看覆蓋率：

```bash
cd apps/backend && uv run python -m pytest tests/ --cov=src --cov-report=term-missing 2>&1
```
