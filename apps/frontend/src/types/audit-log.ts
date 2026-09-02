/** Issue #60 — 設定變更稽核紀錄（system_admin only） */

export type AuditEntityType =
  | "guard_rules"
  | "system_prompt"
  | "bot"
  | "worker"
  | "tenant";

export type AuditAction = "create" | "update" | "delete" | "reset";

export interface AuditFieldChange {
  before: unknown;
  after: unknown;
}

export interface AuditLog {
  id: string;
  tenant_id: string | null;
  actor_user_id: string | null;
  entity_type: AuditEntityType | string;
  entity_id: string | null;
  action: AuditAction | string;
  changed_fields: Record<string, AuditFieldChange>;
  source: string | null;
  created_at: string;
}

export interface PaginatedAuditLogs {
  items: AuditLog[];
  limit: number;
  offset: number;
}

export interface AuditLogFilters {
  tenant_id?: string;
  entity_type?: string;
  entity_id?: string;
  limit: number;
  offset: number;
}
