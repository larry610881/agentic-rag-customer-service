import { useQuery } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api-client";
import { useAuthStore } from "@/stores/use-auth-store";

export interface CategoryChunkItem {
  id: string;
  content: string;
  context_text: string;
  chunk_index: number;
  cohesion_score: number;
}

export interface CategoryChunksResponse {
  category_id: string;
  category_name: string;
  chunk_count: number;
  chunks: CategoryChunkItem[];
}

export function useCategoryChunks(kbId: string, categoryId: string | null) {
  const token = useAuthStore((s) => s.token);

  return useQuery({
    queryKey: ["category-chunks", kbId, categoryId],
    queryFn: () =>
      apiFetch<CategoryChunksResponse>(
        `/api/v1/knowledge-bases/${kbId}/categories/${categoryId}/chunks`,
        {},
        token ?? undefined,
      ),
    enabled: !!token && !!kbId && !!categoryId,
  });
}
