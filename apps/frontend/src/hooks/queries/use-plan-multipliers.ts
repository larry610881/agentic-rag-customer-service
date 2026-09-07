import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api-client";
import { API_ENDPOINTS } from "@/lib/api-endpoints";
import { queryKeys } from "@/hooks/queries/keys";
import { useAuthStore } from "@/stores/use-auth-store";
import type {
  PlanMultipliersResponse,
  ReplacePlanMultipliersRequest,
} from "@/types/billing";

/**
 * Issue #74 — GET /admin/plans/{id}/multipliers
 * 新增模式（planId = null）不查詢；表格從空白開始。
 */
export function usePlanMultipliers(planId: string | null, enabled = true) {
  const token = useAuthStore((s) => s.token);

  return useQuery({
    queryKey: planId
      ? queryKeys.plans.multipliers(planId)
      : (["plans", "none", "multipliers"] as const),
    queryFn: () =>
      apiFetch<PlanMultipliersResponse>(
        API_ENDPOINTS.plans.multipliers(planId as string),
        {},
        token ?? undefined,
      ),
    enabled: !!token && !!planId && enabled,
  });
}

/** PUT /admin/plans/{id}/multipliers — 整份取代 */
export function useReplacePlanMultipliers() {
  const token = useAuthStore((s) => s.token);
  const qc = useQueryClient();

  return useMutation({
    mutationFn: ({
      planId,
      data,
    }: {
      planId: string;
      data: ReplacePlanMultipliersRequest;
    }) =>
      apiFetch<PlanMultipliersResponse>(
        API_ENDPOINTS.plans.multipliers(planId),
        { method: "PUT", body: JSON.stringify(data) },
        token ?? undefined,
      ),
    onSuccess: (_data, { planId }) => {
      qc.invalidateQueries({ queryKey: queryKeys.plans.multipliers(planId) });
    },
  });
}
