import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { apiFetch } from "@/lib/api-client";
import { API_ENDPOINTS } from "@/lib/api-endpoints";
import { useAuthStore } from "@/stores/use-auth-store";
import type { ChunkCategory } from "@/types/knowledge";

export function useCategories(kbId: string, polling = false) {
  const token = useAuthStore((s) => s.token);

  return useQuery({
    queryKey: ["categories", kbId],
    queryFn: () =>
      apiFetch<ChunkCategory[]>(
        API_ENDPOINTS.knowledgeBases.categories(kbId),
        {},
        token ?? undefined,
      ),
    enabled: !!token && !!kbId,
    refetchInterval: polling ? 3000 : false,
  });
}

export function useClassifyKb(kbId: string) {
  const token = useAuthStore((s) => s.token);
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: () =>
      apiFetch<{ status: string; message: string }>(
        API_ENDPOINTS.knowledgeBases.classify(kbId),
        { method: "POST" },
        token ?? undefined,
      ),
    onSuccess: () => {
      toast.success("分類任務已排入佇列");
      queryClient.invalidateQueries({ queryKey: ["categories", kbId] });
    },
    onError: () => {
      toast.error("觸發分類失敗");
    },
  });
}

export function useUpdateCategory(kbId: string) {
  const token = useAuthStore((s) => s.token);
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ catId, name }: { catId: string; name: string }) =>
      apiFetch<ChunkCategory>(
        API_ENDPOINTS.knowledgeBases.updateCategory(kbId, catId),
        { method: "PATCH", body: JSON.stringify({ name }) },
        token ?? undefined,
      ),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["categories", kbId] });
      toast.success("分類已更新");
    },
    onError: () => {
      toast.error("更新分類失敗");
    },
  });
}
