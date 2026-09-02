/** Issue #60 — 生效設定快照（config snapshot）與 bot 設定時間軸 */

export interface GuardInputRule {
  id: string;
  pattern: string;
  enabled: boolean;
}

export interface ConfigSnapshotGuard {
  input_rules: GuardInputRule[];
  output_keywords: string[];
  blocked_response: string;
  llm_guard_enabled: boolean;
  llm_input_guard_enabled: boolean;
}

export interface ConfigSnapshotRetrieval {
  modes: string[];
  rerank_enabled: boolean;
  rerank_model: string | null;
  rerank_top_n?: number | null;
  kb_ids: string[];
  direct_retrieval?: boolean | null;
}

/** 對話當下生效的完整設定；後端以 canonical JSON hash 去重 */
export interface ConfigSnapshot {
  schema: number | string;
  channel: string;
  bot_id: string | null;
  system_prompt: string;
  platform_prompt_fallback: boolean;
  worker_name: string | null;
  llm_provider: string | null;
  llm_model: string | null;
  router_model: string | null;
  llm_params: Record<string, unknown>;
  retrieval: ConfigSnapshotRetrieval;
  enabled_tools: string[];
  max_tool_calls: number | null;
  guard: ConfigSnapshotGuard | null;
  memory_enabled: boolean;
  extra: Record<string, unknown>;
}

export interface ConfigSnapshotRecord {
  hash: string;
  schema: number | string;
  first_seen_at: string;
  snapshot: ConfigSnapshot;
}

export interface ConfigFieldChange {
  before: unknown;
  after: unknown;
}

export interface ConfigSnapshotDiff {
  a: string;
  b: string;
  /** key 為 dotted path，例如 "retrieval.rerank_enabled" */
  changed_fields: Record<string, ConfigFieldChange>;
}

export interface BotConfigTimelineItem {
  hash: string;
  first_seen_at: string;
  last_seen_at: string;
  turns: number;
}

export interface BotConfigTimeline {
  bot_id: string;
  /** 依 first_seen_at 降序（最新在前） */
  items: BotConfigTimelineItem[];
}
