/**
 * S-Gov.6a: Trace ID 短碼 format helper（純前端，schema 不動）
 *
 * 把 UUID `03f4...a1b2` 轉成 `trc_20260421_a1b2` 易讀格式：
 *   - prefix `trc_` 識別 trace
 *   - 中段 `YYYYMMDD` 來自 created_at
 *   - 末段 4 碼取 UUID 前 4 碼（去 dash）
 *
 * 完整 UUID 仍為 source of truth — UI 應 hover 顯示完整、提供複製。
 */

export function formatTraceShortId(
  traceId: string,
  createdAt: string,
): string {
  if (!traceId) return "";
  const date = new Date(createdAt);
  const ymd = Number.isNaN(date.getTime())
    ? "00000000"
    : `${date.getFullYear()}${String(date.getMonth() + 1).padStart(2, "0")}${String(
        date.getDate(),
      ).padStart(2, "0")}`;
  const shortHash = traceId.replace(/-/g, "").substring(0, 4);
  return `trc_${ymd}_${shortHash}`;
}
