import { useQuery } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api-client";
import { API_ENDPOINTS } from "@/lib/api-endpoints";
import { queryKeys } from "@/hooks/queries/keys";
import { useAuthStore } from "@/stores/use-auth-store";

export interface TenantQuota {
  cycle_year_month: string; // "YYYY-MM"
  plan_name: string;
  base_total: number;
  base_remaining: number;
  addon_remaining: number; // 可為負（軟上限）
  total_remaining: number;
  total_used_in_cycle: number;
  included_categories: string[] | null;
}

/** 取得租戶本月 token 額度狀態。後端會自動建本月 ledger 若不存在。 */
export function useTenantQuota(tenantId: string | null, enabled = true) {
  const token = useAuthStore((s) => s.token);

  return useQuery({
    queryKey: tenantId ? queryKeys.tenants.quota(tenantId) : ["tenants", "quota", "none"],
    queryFn: () =>
      apiFetch<TenantQuota>(
        API_ENDPOINTS.tenants.quota(tenantId!),
        {},
        token ?? undefined,
      ),
    enabled: !!token && !!tenantId && enabled,
  });
}
