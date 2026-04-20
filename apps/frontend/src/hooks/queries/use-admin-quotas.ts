import { useQuery } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api-client";
import { API_ENDPOINTS } from "@/lib/api-endpoints";
import { queryKeys } from "@/hooks/queries/keys";
import { useAuthStore } from "@/stores/use-auth-store";

export interface AdminTenantQuotaItem {
  tenant_id: string;
  tenant_name: string;
  plan_name: string;
  cycle_year_month: string;
  base_total: number;
  base_remaining: number;
  addon_remaining: number;
  total_remaining: number;
  total_used_in_cycle: number;
  included_categories: string[] | null;
  has_ledger: boolean;
}

/**
 * 系統管理員專用：取得指定 cycle 所有租戶的額度概況。
 * cycle 為 undefined 時後端預設當月。
 */
export function useAdminTenantsQuotas(cycle?: string, enabled = true) {
  const token = useAuthStore((s) => s.token);

  return useQuery({
    queryKey: queryKeys.admin.tenantsQuotas(cycle ?? "current"),
    queryFn: () =>
      apiFetch<AdminTenantQuotaItem[]>(
        API_ENDPOINTS.adminQuotas.list(cycle),
        {},
        token ?? undefined,
      ),
    enabled: !!token && enabled,
    staleTime: 30_000,
  });
}
