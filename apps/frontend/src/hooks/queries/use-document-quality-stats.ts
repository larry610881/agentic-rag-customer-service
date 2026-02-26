import { useQuery } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api-client";
import { API_ENDPOINTS } from "@/lib/api-endpoints";
import { queryKeys } from "@/hooks/queries/keys";
import { useAuthStore } from "@/stores/use-auth-store";
import type { DocumentQualityStat } from "@/types/knowledge";

export function useDocumentQualityStats(kbId: string, enabled = true) {
  const token = useAuthStore((s) => s.token);

  return useQuery({
    queryKey: queryKeys.documents.qualityStats(kbId),
    queryFn: () =>
      apiFetch<DocumentQualityStat[]>(
        API_ENDPOINTS.documents.qualityStats(kbId),
        {},
        token ?? undefined,
      ),
    enabled: enabled && !!kbId && !!token,
  });
}
