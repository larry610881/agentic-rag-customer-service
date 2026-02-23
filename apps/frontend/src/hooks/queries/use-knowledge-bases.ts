import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api-client";
import { API_ENDPOINTS } from "@/lib/api-endpoints";
import { queryKeys } from "@/hooks/queries/keys";
import { useAuthStore } from "@/stores/use-auth-store";
import type { KnowledgeBase } from "@/types/knowledge";

export function useKnowledgeBases() {
  const token = useAuthStore((s) => s.token);
  const tenantId = useAuthStore((s) => s.tenantId);

  return useQuery({
    queryKey: queryKeys.knowledgeBases.all(tenantId ?? ""),
    queryFn: () =>
      apiFetch<KnowledgeBase[]>(
        API_ENDPOINTS.knowledgeBases.list,
        {},
        token ?? undefined,
      ),
    enabled: !!token && !!tenantId,
  });
}

export function useCreateKnowledgeBase() {
  const token = useAuthStore((s) => s.token);
  const tenantId = useAuthStore((s) => s.tenantId);
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: { name: string; description: string }) =>
      apiFetch<KnowledgeBase>(
        API_ENDPOINTS.knowledgeBases.create,
        { method: "POST", body: JSON.stringify(data) },
        token ?? undefined,
      ),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: queryKeys.knowledgeBases.all(tenantId ?? ""),
      });
    },
  });
}
