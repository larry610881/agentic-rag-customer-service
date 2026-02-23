---
paths:
  - "**/*"
---

# Monorepo 跨 App 規則

## 目錄邊界

- `apps/backend/` 與 `apps/frontend/` 是獨立應用，**禁止互相 import**
- 共用型別定義放 `packages/shared-types/`（未來擴充）
- 基礎設施設定放 `infra/`

## 套件管理

| App | 工具 | Lock 檔案 |
|-----|------|-----------|
| `apps/backend/` | uv | `uv.lock` |
| `apps/frontend/` | npm | `package-lock.json` |

- 禁止在根目錄執行 `pip install` 或 `npm install`
- 統一透過 `Makefile` 操作

## 測試隔離

- 後端測試只在 `apps/backend/` 內執行：`cd apps/backend && uv run python -m pytest`
- 前端測試只在 `apps/frontend/` 內執行：`cd apps/frontend && npx vitest run`
- 全量測試透過 `make test` 統一入口

## 環境變數

- 後端 `.env` 在 `apps/backend/.env`
- 前端 `.env` 在 `apps/frontend/.env.local`
- 共用環境變數（如 Docker Compose）在根目錄 `.env`
- **所有 `.env` 檔案禁止提交至版控**

## Docker Compose

- `docker-compose.yml` 在根目錄
- 後端 `Dockerfile` 在 `apps/backend/Dockerfile`
- 前端 `Dockerfile` 在 `apps/frontend/Dockerfile`
- 服務命名：`backend`、`frontend`、`db`、`redis`、`qdrant`

## 路徑別名

- 後端：使用 Python 絕對 import（`from src.domain.tenant.entity import Tenant`）
- 前端：使用 `@/` 別名對應 `src/`（`import { Button } from '@/components/ui/button'`）
