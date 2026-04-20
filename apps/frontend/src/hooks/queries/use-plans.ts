import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api-client";
import { API_ENDPOINTS } from "@/lib/api-endpoints";
import { queryKeys } from "@/hooks/queries/keys";
import { useAuthStore } from "@/stores/use-auth-store";
import type {
  CreatePlanRequest,
  Plan,
  UpdatePlanRequest,
} from "@/types/plan";

/** List all plans (含 inactive)。前端可自行 filter is_active 給下拉選單用 */
export function usePlans(includeInactive = true) {
  const token = useAuthStore((s) => s.token);

  return useQuery({
    queryKey: [...queryKeys.plans.all, includeInactive] as const,
    queryFn: () =>
      apiFetch<Plan[]>(
        `${API_ENDPOINTS.plans.list}?include_inactive=${includeInactive}`,
        {},
        token ?? undefined,
      ),
    enabled: !!token,
  });
}

export function useCreatePlan() {
  const token = useAuthStore((s) => s.token);
  const qc = useQueryClient();

  return useMutation({
    mutationFn: (data: CreatePlanRequest) =>
      apiFetch<Plan>(
        API_ENDPOINTS.plans.create,
        { method: "POST", body: JSON.stringify(data) },
        token ?? undefined,
      ),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: queryKeys.plans.all });
    },
  });
}

export function useUpdatePlan() {
  const token = useAuthStore((s) => s.token);
  const qc = useQueryClient();

  return useMutation({
    mutationFn: ({
      id,
      data,
    }: {
      id: string;
      data: UpdatePlanRequest;
    }) =>
      apiFetch<Plan>(
        API_ENDPOINTS.plans.update(id),
        { method: "PATCH", body: JSON.stringify(data) },
        token ?? undefined,
      ),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: queryKeys.plans.all });
    },
  });
}

/**
 * 預設軟刪（force=false → set is_active=false）；
 * force=true 嘗試硬刪，若有租戶綁則回 409。
 */
export function useDeletePlan() {
  const token = useAuthStore((s) => s.token);
  const qc = useQueryClient();

  return useMutation({
    mutationFn: ({ id, force = false }: { id: string; force?: boolean }) =>
      apiFetch<void>(
        API_ENDPOINTS.plans.delete(id, force),
        { method: "DELETE" },
        token ?? undefined,
      ),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: queryKeys.plans.all });
    },
  });
}

export function useAssignPlanToTenant() {
  const token = useAuthStore((s) => s.token);
  const qc = useQueryClient();

  return useMutation({
    mutationFn: ({
      planName,
      tenantId,
    }: {
      planName: string;
      tenantId: string;
    }) =>
      apiFetch<void>(
        API_ENDPOINTS.plans.assign(planName, tenantId),
        { method: "POST" },
        token ?? undefined,
      ),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: queryKeys.tenants.all });
    },
  });
}
