/**
 * Outbox Pattern types — Phase E admin DLQ UI
 *
 * 對應 src/interfaces/api/admin_outbox_router.py 的 Pydantic schemas
 */

export type OutboxStatus =
  | "pending"
  | "in_progress"
  | "done"
  | "dead";

export type OutboxEventType =
  | "vector.delete"
  | "vector.drop_collection";

export interface OutboxEvent {
  id: string;
  tenant_id: string;
  aggregate_type: string;
  aggregate_id: string;
  event_type: string;
  payload: Record<string, unknown>;
  status: OutboxStatus;
  attempts: number;
  max_attempts: number;
  last_error: string | null;
  next_attempt_at: string;
  created_at: string;
  completed_at: string | null;
  /** server-side computed: NOW() - created_at, in seconds */
  age_seconds: number;
}

export interface OutboxStats {
  pending_count: number;
  in_progress_count: number;
  done_count: number;
  dead_count: number;
  oldest_pending_age_seconds: number | null;
}

export interface BulkRequeueRequest {
  event_type?: string | null;
  tenant_id?: string | null;
  /** server caps at 500 */
  limit?: number;
}

export interface BulkRequeueResponse {
  requeued_count: number;
  event_ids: string[];
}

export interface ListDeadLetterParams {
  event_type?: string;
  tenant_id?: string;
  limit?: number;
  offset?: number;
}
