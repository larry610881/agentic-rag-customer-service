import { useQuery } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api-client";
import { API_ENDPOINTS } from "@/lib/api-endpoints";
import { queryKeys } from "@/hooks/queries/keys";
import { useAuthStore } from "@/stores/use-auth-store";
import type { TenantBotUsageStat } from "@/types/token-usage";

export function useSystemTokenUsage(days = 30) {
  const token = useAuthStore((s) => s.token);

  return useQuery({
    queryKey: queryKeys.observability.tokenUsage(days),
    queryFn: () =>
      apiFetch<{ items: TenantBotUsageStat[] }>(
        `${API_ENDPOINTS.observability.tokenUsage}?days=${days}`,
        {},
        token ?? undefined,
      ),
    enabled: !!token,
    select: (data) => data.items,
  });
}
