import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api-client";
import { API_ENDPOINTS } from "@/lib/api-endpoints";
import { queryKeys } from "@/hooks/queries/keys";
import { useAuthStore } from "@/stores/use-auth-store";
import type {
  PaginatedEvals,
  DiagnosticRulesConfig,
} from "@/types/observability";

export interface EvalFilters {
  limit: number;
  offset: number;
  tenant_id?: string;
  layer?: string;
  min_score?: number;
}

export function useRAGEvals(filters: EvalFilters) {
  const token = useAuthStore((s) => s.token);
  const params = new URLSearchParams();
  params.set("limit", String(filters.limit));
  params.set("offset", String(filters.offset));
  if (filters.tenant_id) params.set("tenant_id", filters.tenant_id);
  if (filters.layer) params.set("layer", filters.layer);
  if (filters.min_score !== undefined) params.set("min_score", String(filters.min_score));

  return useQuery({
    queryKey: queryKeys.observability.evals(filters),
    queryFn: () =>
      apiFetch<PaginatedEvals>(
        `${API_ENDPOINTS.observability.evaluations}?${params.toString()}`,
        {},
        token ?? undefined,
      ),
    enabled: !!token,
    refetchInterval: 10_000,
  });
}

// --- Diagnostic Rules ---

export function useDiagnosticRules() {
  const token = useAuthStore((s) => s.token);

  return useQuery({
    queryKey: queryKeys.observability.diagnosticRules,
    queryFn: () =>
      apiFetch<DiagnosticRulesConfig>(
        API_ENDPOINTS.observability.diagnosticRules,
        {},
        token ?? undefined,
      ),
    enabled: !!token,
  });
}

export function useUpdateDiagnosticRules() {
  const token = useAuthStore((s) => s.token);
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: Pick<DiagnosticRulesConfig, "single_rules" | "combo_rules">) =>
      apiFetch<DiagnosticRulesConfig>(
        API_ENDPOINTS.observability.diagnosticRules,
        { method: "PUT", body: JSON.stringify(data) },
        token ?? undefined,
      ),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: queryKeys.observability.diagnosticRules,
      });
    },
  });
}

export function useResetDiagnosticRules() {
  const token = useAuthStore((s) => s.token);
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: () =>
      apiFetch<DiagnosticRulesConfig>(
        API_ENDPOINTS.observability.resetDiagnosticRules,
        { method: "POST" },
        token ?? undefined,
      ),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: queryKeys.observability.diagnosticRules,
      });
    },
  });
}
