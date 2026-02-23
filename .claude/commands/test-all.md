# 執行全部測試

依序執行後端和前端的完整測試套件，並彙整結果。

## 使用方式

- `/test-all` — 執行所有測試（後端 + 前端）
- `/test-all --coverage` — 含覆蓋率報告

## 執行步驟

### 1. 後端測試

```bash
cd apps/backend && uv run python -m pytest tests/ -v --tb=short 2>&1
```

若 `$ARGUMENTS` 包含 `--coverage`：
```bash
cd apps/backend && uv run python -m pytest tests/ --cov=src --cov-report=term-missing --tb=short 2>&1
```

### 2. 前端測試

```bash
cd apps/frontend && npx vitest run --reporter=verbose 2>&1
```

若 `$ARGUMENTS` 包含 `--coverage`：
```bash
cd apps/frontend && npx vitest run --coverage 2>&1
```

### 3. 彙整結果

輸出格式：

```
## 全量測試結果

### 後端
- 總數: X tests
- 通過: X ✅ / 失敗: X ❌
- 覆蓋率: XX%

### 前端
- 總數: X tests
- 通過: X ✅ / 失敗: X ❌
- 覆蓋率: XX%

### 總結
- 狀態: 全部通過 / 有失敗
- 需要修復: [列出失敗項目]
```
