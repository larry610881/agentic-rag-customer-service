/** Issue #71 — 租戶端 bot 變更紀錄（GET /bots/{id}/audit-logs） */

/** 一般欄位：伺服端已攤平（llm_params.temperature），附前後值 */
export interface BotAuditValueChange {
  field: string;
  before: unknown;
  after: unknown;
}

/** 長文字欄位（提示詞類）：只回字數，不回全文 */
export interface BotAuditLongTextChange {
  field: string;
  before_len: number;
  after_len: number;
  changed: true;
}

export type BotAuditChange = BotAuditValueChange | BotAuditLongTextChange;

export function isLongTextChange(
  change: BotAuditChange,
): change is BotAuditLongTextChange {
  return "before_len" in change || "after_len" in change;
}

export interface BotAuditLogEntry {
  id: string;
  action: "create" | "update" | "delete" | "reset" | string;
  actor_user_id: string | null;
  actor_email: string | null;
  /** Issue #75 — 平台（system_admin）對該租戶的防護階段變更標「平台」 */
  actor_label?: string | null;
  /** Issue #75 — bot | guard_settings（租戶 scope 的防護設定變更） */
  entity_type?: "bot" | "guard_settings" | string;
  source: string | null;
  created_at: string;
  changes: BotAuditChange[];
}

export interface BotAuditLogPage {
  items: BotAuditLogEntry[];
  next_cursor: string | null;
}
