/**
 * API Base URL — 全域共用常數
 *
 * 使用情境與行為：
 * ┌──────────────────────┬────────────────────────┬────────────────────────────┐
 * │ 情境                 │ VITE_API_URL           │ API_BASE 結果              │
 * ├──────────────────────┼────────────────────────┼────────────────────────────┤
 * │ Dev（Vite proxy）    │ 未設定                 │ ""（相對路徑走 proxy）      │
 * │ Dev（直連後端）      │ http://localhost:8001   │ http://localhost:8001       │
 * │ E2E（Playwright）    │ 未設定                 │ ""（走 Vite proxy）         │
 * │ Prod（同 origin）    │ 未設定                 │ ""（Nginx 反向代理）        │
 * │ Prod（跨 origin）    │ https://api.example.com│ https://api.example.com    │
 * └──────────────────────┴────────────────────────┴────────────────────────────┘
 *
 * 注入方式：
 * - Vite 環境變數 `VITE_API_URL`（.env.local 或 CLI）
 * - 未設定時預設為 "" → 所有 fetch 使用相對路徑，由 Vite dev proxy 或
 *   production reverse proxy 轉發至後端
 *
 * 使用此常數的模組：
 * - api-client.ts    — 標準 JSON fetch（apiFetch）
 * - use-streaming.ts — SSE 串流（fetchSSE，因 EventSource 無法用 apiFetch）
 * - use-documents.ts — 檔案上傳/刪除（FormData，無法加 Content-Type: application/json）
 */
export const API_BASE = (import.meta.env.VITE_API_URL || "").replace(
  /\/+$/,
  "",
);

/**
 * Public API URL — 給外部使用的完整 URL
 *
 * 用於產生嵌入碼（Widget embed code）、Webhook URL 等需要完整 URL 的場景。
 * 這些 URL 會被複製到外部網站使用，不能用相對路徑。
 *
 * 與 API_BASE 的區別：
 * - API_BASE：前端內部 fetch 用，可以是 ""（相對路徑）
 * - PUBLIC_API_URL：給外部系統用，必須是完整 URL
 */
export const PUBLIC_API_URL = (
  import.meta.env.VITE_API_URL || "http://localhost:8001"
).replace(/\/+$/, "");
