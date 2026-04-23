import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api-client";
import { API_ENDPOINTS } from "@/lib/api-endpoints";
import { queryKeys } from "@/hooks/queries/keys";
import { useAuthStore } from "@/stores/use-auth-store";
import type { CollectionInfo, CollectionStats } from "@/types/milvus";

export function useMilvusCollections() {
  const token = useAuthStore((s) => s.token);
  return useQuery({
    queryKey: queryKeys.milvusAdmin.collections,
    queryFn: () =>
      apiFetch<CollectionInfo[]>(
        API_ENDPOINTS.adminMilvus.collections,
        {},
        token ?? undefined,
      ),
    enabled: !!token,
  });
}

export function useCollectionStats(name: string | null) {
  const token = useAuthStore((s) => s.token);
  return useQuery({
    queryKey: queryKeys.milvusAdmin.stats(name ?? ""),
    queryFn: () =>
      apiFetch<CollectionStats>(
        API_ENDPOINTS.adminMilvus.stats(name!),
        {},
        token ?? undefined,
      ),
    enabled: !!token && !!name,
  });
}

export function useRebuildIndex() {
  const token = useAuthStore((s) => s.token);
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (name: string) =>
      apiFetch<Record<string, unknown>>(
        API_ENDPOINTS.adminMilvus.rebuildIndex(name),
        { method: "POST" },
        token ?? undefined,
      ),
    onSuccess: (_, name) => {
      qc.invalidateQueries({ queryKey: queryKeys.milvusAdmin.stats(name) });
      qc.invalidateQueries({ queryKey: queryKeys.milvusAdmin.collections });
    },
  });
}
