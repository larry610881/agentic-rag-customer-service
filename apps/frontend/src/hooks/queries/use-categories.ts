import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api-client";
import { API_ENDPOINTS } from "@/lib/api-endpoints";
import { queryKeys } from "@/hooks/queries/keys";
import { useAuthStore } from "@/stores/use-auth-store";
import type { ChunkCategory } from "@/types/chunk";

export function useCategoriesQuery(kbId: string) {
  const token = useAuthStore((s) => s.token);
  return useQuery({
    queryKey: queryKeys.categories.list(kbId),
    queryFn: () =>
      apiFetch<ChunkCategory[]>(
        API_ENDPOINTS.categories.list(kbId),
        {},
        token ?? undefined,
      ),
    enabled: !!token && !!kbId,
  });
}

export function useCreateCategory(kbId: string) {
  const token = useAuthStore((s) => s.token);
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: { name: string; description?: string }) =>
      apiFetch<ChunkCategory>(
        API_ENDPOINTS.categories.create(kbId),
        { method: "POST", body: JSON.stringify(data) },
        token ?? undefined,
      ),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: queryKeys.categories.list(kbId) });
    },
  });
}

export function useDeleteCategory(kbId: string) {
  const token = useAuthStore((s) => s.token);
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (catId: string) =>
      apiFetch<void>(
        API_ENDPOINTS.categories.delete(kbId, catId),
        { method: "DELETE" },
        token ?? undefined,
      ),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: queryKeys.categories.list(kbId) });
      qc.invalidateQueries({
        queryKey: ["kb-studio", "chunks", kbId] as const,
      });
    },
  });
}

export function useAssignChunks(kbId: string) {
  const token = useAuthStore((s) => s.token);
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ catId, chunkIds }: { catId: string; chunkIds: string[] }) =>
      apiFetch<{ status: string; assigned_count: number }>(
        API_ENDPOINTS.categories.assignChunks(kbId, catId),
        { method: "POST", body: JSON.stringify({ chunk_ids: chunkIds }) },
        token ?? undefined,
      ),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: queryKeys.categories.list(kbId) });
      qc.invalidateQueries({
        queryKey: ["kb-studio", "chunks", kbId] as const,
      });
    },
  });
}
