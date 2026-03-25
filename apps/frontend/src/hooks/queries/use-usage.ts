import { useQuery } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api-client";
import { API_ENDPOINTS } from "@/lib/api-endpoints";
import { queryKeys } from "@/hooks/queries/keys";
import { useAuthStore } from "@/stores/use-auth-store";
import type { BotUsageStat, DailyUsageStat, MonthlyUsageStat } from "@/types/token-usage";

export function useBotUsage(startDate: string, endDate: string) {
  const token = useAuthStore((s) => s.token);
  const tenantId = useAuthStore((s) => s.tenantId);

  return useQuery({
    queryKey: queryKeys.usage.byBot(tenantId ?? "", startDate, endDate),
    queryFn: () =>
      apiFetch<BotUsageStat[]>(
        `${API_ENDPOINTS.usage.byBot}?start_date=${startDate}&end_date=${endDate}`,
        {},
        token ?? undefined,
      ),
    enabled: !!token && !!tenantId,
  });
}

export function useDailyUsage(startDate: string, endDate: string) {
  const token = useAuthStore((s) => s.token);
  const tenantId = useAuthStore((s) => s.tenantId);

  return useQuery({
    queryKey: queryKeys.usage.daily(tenantId ?? "", startDate, endDate),
    queryFn: () =>
      apiFetch<DailyUsageStat[]>(
        `${API_ENDPOINTS.usage.daily}?start_date=${startDate}&end_date=${endDate}`,
        {},
        token ?? undefined,
      ),
    enabled: !!token && !!tenantId,
  });
}

export function useMonthlyUsage(startDate: string, endDate: string) {
  const token = useAuthStore((s) => s.token);
  const tenantId = useAuthStore((s) => s.tenantId);

  return useQuery({
    queryKey: queryKeys.usage.monthly(tenantId ?? "", startDate, endDate),
    queryFn: () =>
      apiFetch<MonthlyUsageStat[]>(
        `${API_ENDPOINTS.usage.monthly}?start_date=${startDate}&end_date=${endDate}`,
        {},
        token ?? undefined,
      ),
    enabled: !!token && !!tenantId,
  });
}
