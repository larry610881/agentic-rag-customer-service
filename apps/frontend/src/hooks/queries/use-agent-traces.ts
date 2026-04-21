import { useQuery } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api-client";
import { API_ENDPOINTS } from "@/lib/api-endpoints";
import { queryKeys } from "@/hooks/queries/keys";
import { useAuthStore } from "@/stores/use-auth-store";
import type {
  AgentExecutionTrace,
  GroupedAgentTraces,
  PaginatedAgentTraces,
  TraceOutcome,
} from "@/types/agent-trace";

export type AgentTraceFilters = {
  limit: number;
  offset: number;
  tenant_id?: string;
  agent_mode?: string;
  conversation_id?: string;
  date_from?: string;
  date_to?: string;
  // S-Gov.6a: 7 個新 filter
  source?: string;
  bot_id?: string;
  outcome?: TraceOutcome;
  min_total_ms?: number;
  max_total_ms?: number;
  min_total_tokens?: number;
  max_total_tokens?: number;
  keyword?: string;
  group_by_conversation?: boolean;
};

function buildParams(filters: AgentTraceFilters): URLSearchParams {
  const params = new URLSearchParams();
  params.set("limit", String(filters.limit));
  params.set("offset", String(filters.offset));
  if (filters.tenant_id) params.set("tenant_id", filters.tenant_id);
  if (filters.agent_mode) params.set("agent_mode", filters.agent_mode);
  if (filters.conversation_id)
    params.set("conversation_id", filters.conversation_id);
  if (filters.date_from) params.set("date_from", filters.date_from);
  if (filters.date_to) params.set("date_to", filters.date_to);
  if (filters.source) params.set("source", filters.source);
  if (filters.bot_id) params.set("bot_id", filters.bot_id);
  if (filters.outcome) params.set("outcome", filters.outcome);
  if (filters.min_total_ms !== undefined)
    params.set("min_total_ms", String(filters.min_total_ms));
  if (filters.max_total_ms !== undefined)
    params.set("max_total_ms", String(filters.max_total_ms));
  if (filters.min_total_tokens !== undefined)
    params.set("min_total_tokens", String(filters.min_total_tokens));
  if (filters.max_total_tokens !== undefined)
    params.set("max_total_tokens", String(filters.max_total_tokens));
  if (filters.keyword) params.set("keyword", filters.keyword);
  if (filters.group_by_conversation)
    params.set("group_by_conversation", "true");
  return params;
}

/** Flat 模式：回 trace 列表（既有用法）。 */
export function useAgentTraces(filters: AgentTraceFilters) {
  const token = useAuthStore((s) => s.token);
  const params = buildParams({ ...filters, group_by_conversation: false });

  return useQuery({
    queryKey: queryKeys.observability.agentTraces(filters),
    queryFn: () =>
      apiFetch<PaginatedAgentTraces>(
        `${API_ENDPOINTS.observability.agentTraces}?${params.toString()}`,
        {},
        token ?? undefined,
      ),
    enabled: !!token,
    refetchInterval: 10_000,
  });
}

/** S-Gov.6a: Grouped 模式 — 回每個 conversation 的 trace 聚合 */
export function useAgentTracesGrouped(filters: AgentTraceFilters) {
  const token = useAuthStore((s) => s.token);
  const params = buildParams({ ...filters, group_by_conversation: true });

  return useQuery({
    queryKey: queryKeys.observability.agentTracesGrouped(filters),
    queryFn: () =>
      apiFetch<GroupedAgentTraces>(
        `${API_ENDPOINTS.observability.agentTraces}?${params.toString()}`,
        {},
        token ?? undefined,
      ),
    enabled: !!token,
    refetchInterval: 10_000,
  });
}

export function useAgentTraceDetail(traceId: string | null) {
  const token = useAuthStore((s) => s.token);

  return useQuery({
    queryKey: queryKeys.observability.agentTraceDetail(traceId ?? ""),
    queryFn: () =>
      apiFetch<AgentExecutionTrace>(
        API_ENDPOINTS.observability.agentTraceDetail(traceId!),
        {},
        token ?? undefined,
      ),
    enabled: !!token && !!traceId,
  });
}
