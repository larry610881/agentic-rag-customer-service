# Backend — DDD 4-Layer FastAPI + LangGraph

> DDD 分層規則、測試策略、BDD 範例等詳見 `.claude/rules/python-standards.md`。

## 套件管理

```bash
uv sync                    # 安裝依賴
uv add <package>           # 新增套件
uv add --dev <package>     # 新增開發套件
uv run <command>           # 執行指令
```

## 測試

```bash
# 全量測試
uv run python -m pytest tests/ -v --tb=short

# 覆蓋率
uv run python -m pytest tests/ --cov=src --cov-report=term-missing

# 指定範圍
uv run python -m pytest tests/unit/knowledge/ -v

# Lint
uv run ruff check src/
uv run mypy src/
```

## DI Container

- 使用 `dependency-injector`
- 所有 Repository 和 Use Case 在 Container 註冊
- Interfaces 層透過 `@inject` + `Depends(Provide[Container.xxx])` 注入
