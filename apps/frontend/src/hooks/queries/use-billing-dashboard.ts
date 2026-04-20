import { useQuery } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api-client";
import { API_ENDPOINTS } from "@/lib/api-endpoints";
import { queryKeys } from "@/hooks/queries/keys";
import { useAuthStore } from "@/stores/use-auth-store";

export interface MonthlyRevenuePoint {
  cycle_year_month: string;
  total_amount: string; // Decimal serialized
  transaction_count: number;
  addon_tokens_total: number;
}

export interface PlanRevenuePoint {
  plan_name: string;
  total_amount: string;
  transaction_count: number;
}

export interface TopTenantItem {
  tenant_id: string;
  tenant_name: string;
  total_amount: string;
  transaction_count: number;
}

export interface BillingDashboard {
  monthly_revenue: MonthlyRevenuePoint[];
  by_plan: PlanRevenuePoint[];
  top_tenants: TopTenantItem[];
  total_revenue: string;
  total_transactions: number;
  cycle_start: string;
  cycle_end: string;
}

interface UseBillingDashboardParams {
  start?: string;
  end?: string;
  topN?: number;
  enabled?: boolean;
}

/**
 * 系統管理員專用：取得月營收 / plan 分布 / top 租戶聚合資料。
 */
export function useBillingDashboard({
  start,
  end,
  topN = 10,
  enabled = true,
}: UseBillingDashboardParams = {}) {
  const token = useAuthStore((s) => s.token);

  return useQuery({
    queryKey: queryKeys.admin.billingDashboard(
      start ?? "default",
      end ?? "default",
      topN,
    ),
    queryFn: () =>
      apiFetch<BillingDashboard>(
        API_ENDPOINTS.adminBilling.dashboard({ start, end, topN }),
        {},
        token ?? undefined,
      ),
    enabled: !!token && enabled,
    staleTime: 60_000,
  });
}
