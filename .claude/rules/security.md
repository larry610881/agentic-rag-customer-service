---
paths:
  - "**/*"
---

# 安全規範（全棧 + RAG）

## 敏感資料保護

- **禁止硬編碼** 任何密鑰、token、密碼、API key 於程式碼中
- 環境變數透過 `.env` 檔案管理，**不可提交至版控**
- 後端環境變數在 `apps/backend/.env`
- 前端環境變數使用 `NEXT_PUBLIC_` 前綴，在 `apps/frontend/.env.local`

## 後端安全

### SQL Injection 防護
- f-string 或 `.format()` 拼接 SQL 語句 → **CRITICAL 違規**
- Repository 必須使用 SQLAlchemy ORM 的參數綁定
- `text()` 中使用未參數化的變數 → **CRITICAL 違規**

### 認證與授權
- 所有 API 端點必須包含認證 middleware（排除公開端點）
- JWT token 驗證必須完整（簽名、過期、issuer）
- 權限檢查不可被繞過

### 輸入驗證
- API 端點必須使用 Pydantic Schema 驗證請求
- 路徑參數必須限制型別/範圍
- 檔案上傳必須檢查大小/類型

### CORS
- 正式環境禁止 `allow_origins=["*"]`
- 限制 `allow_methods` / `allow_headers` 為必要項目

## 前端安全

### XSS 防護
- 使用 React 內建的自動 escape 機制
- **禁止使用 `dangerouslySetInnerHTML`**
- 若有不可避免的 HTML 渲染需求，必須使用 DOMPurify 消毒

### 輸入驗證
- 所有外部輸入（使用者輸入、URL 參數、API 回應）必須驗證
- 使用 Zod 定義驗證 schema
- 表單驗證需同時在前端與後端執行

### API 安全
- API 請求必須攜帶適當的認證 token
- 使用 HTTPS 連線
- 避免在 URL query string 傳遞敏感資料

## RAG 安全（特殊）

### Prompt Injection 防護
- **使用者輸入不得直接拼入 System Prompt** — 必須經過 sanitize 處理
- RAG 檢索結果在注入 Prompt 前，必須過濾可能的注入指令
- System Prompt 與使用者訊息必須明確分隔（使用 message role 區分）
- 禁止在 Prompt 中暴露內部系統指令或 Tool 呼叫格式

### 租戶隔離
- **所有向量搜尋必須包含 `tenant_id` 過濾條件** — 防止跨租戶資料洩漏
- 知識庫 CRUD 操作必須驗證 `tenant_id` 歸屬
- Qdrant collection 命名包含 tenant 前綴，或使用 payload filter
- 文件上傳/刪除必須驗證操作者所屬租戶

### Embedding 安全
- Embedding API key 透過環境變數管理，禁止硬編碼
- 批次 Embedding 請求需設定 rate limit
- 快取 embedding 結果時，需考慮租戶隔離

## 依賴管理

- 後端：定期執行 `uv audit`（或 `pip-audit`）
- 前端：定期執行 `npm audit`
- 審查新依賴的安全性與維護狀態
- 禁止安裝不必要的依賴
