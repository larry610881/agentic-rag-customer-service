import { useQuery } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api-client";
import { API_ENDPOINTS } from "@/lib/api-endpoints";
import { queryKeys } from "@/hooks/queries/keys";
import { useAuthStore } from "@/stores/use-auth-store";
import type { ChunkPreviewResponse } from "@/types/knowledge";

export function useDocumentChunks(
  kbId: string,
  docId: string,
  enabled = false,
) {
  const token = useAuthStore((s) => s.token);

  return useQuery({
    queryKey: queryKeys.documents.chunks(kbId, docId),
    queryFn: () =>
      apiFetch<ChunkPreviewResponse>(
        API_ENDPOINTS.documents.chunks(kbId, docId),
        {},
        token ?? undefined,
      ),
    enabled: enabled && !!kbId && !!docId && !!token,
  });
}
