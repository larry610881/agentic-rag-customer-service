import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api-client";
import { API_ENDPOINTS } from "@/lib/api-endpoints";
import { queryKeys } from "@/hooks/queries/keys";
import { useAuthStore } from "@/stores/use-auth-store";
import type {
  CreatePricingRequest,
  DryRunRecalcRequest,
  DryRunRecalcResult,
  ExecuteRecalcRequest,
  ExecuteRecalcResult,
  ModelPricing,
  PricingRecalcAudit,
} from "@/types/pricing";

type ListFilters = { provider?: string; category?: string };

export function useListPricing(filters: ListFilters = {}) {
  const token = useAuthStore((s) => s.token);
  const params = new URLSearchParams();
  if (filters.provider) params.set("provider", filters.provider);
  if (filters.category) params.set("category", filters.category);
  const qs = params.toString();
  const url = qs
    ? `${API_ENDPOINTS.pricing.list}?${qs}`
    : API_ENDPOINTS.pricing.list;

  return useQuery({
    queryKey: queryKeys.pricing.list(filters),
    queryFn: () => apiFetch<ModelPricing[]>(url, {}, token ?? undefined),
    enabled: !!token,
  });
}

export function useCreatePricing() {
  const token = useAuthStore((s) => s.token);
  const qc = useQueryClient();

  return useMutation({
    mutationFn: (data: CreatePricingRequest) =>
      apiFetch<ModelPricing>(
        API_ENDPOINTS.pricing.create,
        { method: "POST", body: JSON.stringify(data) },
        token ?? undefined,
      ),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: queryKeys.pricing.all });
    },
  });
}

export function useDeactivatePricing() {
  const token = useAuthStore((s) => s.token);
  const qc = useQueryClient();

  return useMutation({
    mutationFn: (id: string) =>
      apiFetch<ModelPricing>(
        API_ENDPOINTS.pricing.deactivate(id),
        { method: "POST" },
        token ?? undefined,
      ),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: queryKeys.pricing.all });
    },
  });
}

export function useDryRunRecalculate() {
  const token = useAuthStore((s) => s.token);

  return useMutation({
    mutationFn: (data: DryRunRecalcRequest) =>
      apiFetch<DryRunRecalcResult>(
        API_ENDPOINTS.pricing.recalculateDryRun,
        { method: "POST", body: JSON.stringify(data) },
        token ?? undefined,
      ),
  });
}

export function useExecuteRecalculate() {
  const token = useAuthStore((s) => s.token);
  const qc = useQueryClient();

  return useMutation({
    mutationFn: (data: ExecuteRecalcRequest) =>
      apiFetch<ExecuteRecalcResult>(
        API_ENDPOINTS.pricing.recalculateExecute,
        { method: "POST", body: JSON.stringify(data) },
        token ?? undefined,
      ),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: queryKeys.pricing.recalcHistory });
    },
  });
}

export function useRecalcHistory() {
  const token = useAuthStore((s) => s.token);

  return useQuery({
    queryKey: queryKeys.pricing.recalcHistory,
    queryFn: () =>
      apiFetch<PricingRecalcAudit[]>(
        API_ENDPOINTS.pricing.recalcHistory,
        {},
        token ?? undefined,
      ),
    enabled: !!token,
  });
}
