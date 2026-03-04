import { useQuery } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api-client";
import { API_ENDPOINTS } from "@/lib/api-endpoints";
import { queryKeys } from "@/hooks/queries/keys";
import { useAuthStore } from "@/stores/use-auth-store";

export interface TraceStep {
  step: string;
  elapsed_ms: number;
  sql?: string;
}

export interface RequestLogItem {
  id: string;
  request_id: string;
  method: string;
  path: string;
  status_code: number;
  elapsed_ms: number;
  trace_steps: TraceStep[] | null;
  created_at: string;
}

interface RequestLogsResponse {
  total: number;
  items: RequestLogItem[];
}

export interface LogFilters {
  limit: number;
  offset: number;
  path?: string;
  min_elapsed_ms?: number;
}

export function useRequestLogs(filters: LogFilters) {
  const token = useAuthStore((s) => s.token);

  const params = new URLSearchParams();
  params.set("limit", String(filters.limit));
  params.set("offset", String(filters.offset));
  if (filters.path) params.set("path", filters.path);
  if (filters.min_elapsed_ms !== undefined)
    params.set("min_elapsed_ms", String(filters.min_elapsed_ms));

  return useQuery({
    queryKey: queryKeys.logs.all(filters),
    queryFn: () =>
      apiFetch<RequestLogsResponse>(
        `${API_ENDPOINTS.logs.list}?${params.toString()}`,
        {},
        token ?? undefined,
      ),
    enabled: !!token,
    refetchInterval: 10_000,
  });
}

export function useRequestLogDetail(requestId: string | null) {
  const token = useAuthStore((s) => s.token);

  return useQuery({
    queryKey: queryKeys.logs.detail(requestId ?? ""),
    queryFn: () =>
      apiFetch<RequestLogItem>(
        API_ENDPOINTS.logs.detail(requestId!),
        {},
        token ?? undefined,
      ),
    enabled: !!token && !!requestId,
  });
}
