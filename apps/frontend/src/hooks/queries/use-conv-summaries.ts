import { useMutation, useQuery } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api-client";
import { API_ENDPOINTS } from "@/lib/api-endpoints";
import { queryKeys } from "@/hooks/queries/keys";
import { useAuthStore } from "@/stores/use-auth-store";
import type {
  ConvSummaryListResponse,
  ConvSummarySearchRequest,
  ConvSummarySearchResponse,
} from "@/types/conv-summary";

export function useConvSummaries(
  tenantId: string | null,
  botId?: string | null,
) {
  const token = useAuthStore((s) => s.token);
  return useQuery({
    queryKey: queryKeys.convSummaryAdmin.list(tenantId ?? "", botId),
    queryFn: () =>
      apiFetch<ConvSummaryListResponse>(
        API_ENDPOINTS.adminConvSummary.list(tenantId!, botId ?? null),
        {},
        token ?? undefined,
      ),
    enabled: !!token && !!tenantId,
  });
}

export function useConvSummarySearch() {
  const token = useAuthStore((s) => s.token);
  return useMutation({
    mutationFn: (body: ConvSummarySearchRequest) =>
      apiFetch<ConvSummarySearchResponse>(
        API_ENDPOINTS.adminConvSummary.search,
        { method: "POST", body: JSON.stringify(body) },
        token ?? undefined,
      ),
  });
}
