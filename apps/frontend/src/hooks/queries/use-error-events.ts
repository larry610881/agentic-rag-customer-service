import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api-client";
import { API_ENDPOINTS } from "@/lib/api-endpoints";
import { queryKeys } from "@/hooks/queries/keys";
import { useAuthStore } from "@/stores/use-auth-store";
import type {
  ErrorEvent,
  ErrorEventListResponse,
  ReportErrorPayload,
} from "@/types/error-event";

interface ErrorEventFilters {
  source?: string;
  resolved?: string;
  method?: string;
  limit?: number;
  offset?: number;
}

export function useErrorEvents(filters: ErrorEventFilters = {}) {
  const token = useAuthStore((s) => s.token);
  const role = useAuthStore((s) => s.role);

  const params = new URLSearchParams();
  if (filters.source && filters.source !== "all")
    params.set("source", filters.source);
  if (filters.resolved && filters.resolved !== "all")
    params.set("resolved", filters.resolved);
  if (filters.method && filters.method !== "all")
    params.set("method", filters.method);
  if (filters.limit) params.set("limit", String(filters.limit));
  if (filters.offset) params.set("offset", String(filters.offset));

  const qs = params.toString();
  const url = qs
    ? `${API_ENDPOINTS.errorEvents.list}?${qs}`
    : API_ENDPOINTS.errorEvents.list;

  return useQuery({
    queryKey: queryKeys.errorEvents.all(filters),
    queryFn: () =>
      apiFetch<ErrorEventListResponse>(url, {}, token ?? undefined),
    enabled: !!token && role === "system_admin",
  });
}

export function useErrorEventDetail(id: string) {
  const token = useAuthStore((s) => s.token);

  return useQuery({
    queryKey: queryKeys.errorEvents.detail(id),
    queryFn: () =>
      apiFetch<ErrorEvent>(
        API_ENDPOINTS.errorEvents.detail(id),
        {},
        token ?? undefined,
      ),
    enabled: !!token && !!id,
  });
}

export function useResolveErrorEvent() {
  const token = useAuthStore((s) => s.token);
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (id: string) =>
      apiFetch<ErrorEvent>(
        API_ENDPOINTS.errorEvents.resolve(id),
        { method: "PATCH" },
        token ?? undefined,
      ),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["error-events"] });
    },
  });
}

export function useReportError() {
  return useMutation({
    mutationFn: (payload: ReportErrorPayload) =>
      apiFetch<void>(API_ENDPOINTS.errorEvents.report, {
        method: "POST",
        body: JSON.stringify(payload),
      }),
  });
}
