import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api-client";
import { API_ENDPOINTS } from "@/lib/api-endpoints";
import { queryKeys } from "@/hooks/queries/keys";
import { useAuthStore } from "@/stores/use-auth-store";
import type {
  SystemPromptConfig,
  UpdateSystemPromptConfigRequest,
} from "@/types/platform";

export function useSystemPrompts() {
  const token = useAuthStore((s) => s.token);

  return useQuery({
    queryKey: queryKeys.systemPrompts.all,
    queryFn: () =>
      apiFetch<SystemPromptConfig>(
        API_ENDPOINTS.systemPrompts.get,
        {},
        token ?? undefined,
      ),
    enabled: !!token,
  });
}

export function useUpdateSystemPrompts() {
  const token = useAuthStore((s) => s.token);
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: UpdateSystemPromptConfigRequest) =>
      apiFetch<SystemPromptConfig>(
        API_ENDPOINTS.systemPrompts.update,
        { method: "PUT", body: JSON.stringify(data) },
        token ?? undefined,
      ),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: queryKeys.systemPrompts.all,
      });
    },
  });
}
