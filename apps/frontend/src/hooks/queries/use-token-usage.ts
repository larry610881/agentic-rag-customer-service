import { useQuery } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api-client";
import { API_ENDPOINTS } from "@/lib/api-endpoints";
import { queryKeys } from "@/hooks/queries/keys";
import { useAuthStore } from "@/stores/use-auth-store";
import type { TenantBotUsageStat } from "@/types/token-usage";

export function useSystemTokenUsage(days = 30, tenantId?: string) {
  const token = useAuthStore((s) => s.token);

  const params = new URLSearchParams();
  params.set("days", String(days));
  if (tenantId) params.set("tenant_id", tenantId);

  return useQuery({
    queryKey: queryKeys.observability.tokenUsage(days, tenantId),
    queryFn: () =>
      apiFetch<{ items: TenantBotUsageStat[] }>(
        `${API_ENDPOINTS.observability.tokenUsage}?${params.toString()}`,
        {},
        token ?? undefined,
      ),
    enabled: !!token,
    select: (data) => data.items,
  });
}
