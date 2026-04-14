import { useQuery } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api-client";
import { API_ENDPOINTS } from "@/lib/api-endpoints";
import { queryKeys } from "@/hooks/queries/keys";
import { useAuthStore } from "@/stores/use-auth-store";
import type {
  PaginatedAgentTraces,
  AgentExecutionTrace,
} from "@/types/agent-trace";

export type AgentTraceFilters = {
  limit: number;
  offset: number;
  tenant_id?: string;
  agent_mode?: string;
  conversation_id?: string;
  date_from?: string;
  date_to?: string;
};

export function useAgentTraces(filters: AgentTraceFilters) {
  const token = useAuthStore((s) => s.token);
  const params = new URLSearchParams();
  params.set("limit", String(filters.limit));
  params.set("offset", String(filters.offset));
  if (filters.tenant_id) params.set("tenant_id", filters.tenant_id);
  if (filters.agent_mode) params.set("agent_mode", filters.agent_mode);
  if (filters.conversation_id)
    params.set("conversation_id", filters.conversation_id);
  if (filters.date_from) params.set("date_from", filters.date_from);
  if (filters.date_to) params.set("date_to", filters.date_to);

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
