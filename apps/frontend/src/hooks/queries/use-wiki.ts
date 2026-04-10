import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { apiFetch } from "@/lib/api-client";
import { API_ENDPOINTS } from "@/lib/api-endpoints";
import { queryKeys } from "@/hooks/queries/keys";
import { useAuthStore } from "@/stores/use-auth-store";
import type {
  CompileWikiResponse,
  KnowledgeMode,
  WikiStatusResponse,
} from "@/types/bot";

/**
 * Query Wiki status with smart polling:
 * - Polls every 3 seconds while status === "compiling"
 * - Stops polling on terminal states (ready / stale / failed / pending)
 * - Only enabled when bot uses Wiki mode
 */
export function useWikiStatus(
  botId: string | undefined,
  knowledgeMode: KnowledgeMode | undefined,
) {
  const token = useAuthStore((s) => s.token);

  return useQuery<WikiStatusResponse>({
    queryKey: queryKeys.wiki.status(botId ?? ""),
    queryFn: () =>
      apiFetch<WikiStatusResponse>(
        API_ENDPOINTS.bots.wikiStatus(botId ?? ""),
        {},
        token ?? undefined,
      ),
    enabled: !!token && !!botId && knowledgeMode === "wiki",
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      return status === "compiling" ? 3000 : false;
    },
    // Don't throw on 404 — wiki may simply not exist yet
    retry: false,
  });
}

/**
 * Trigger Wiki compilation. Backend returns 202 Accepted and runs the
 * compilation in a background task. Use `useWikiStatus` to poll progress.
 */
export function useCompileWiki() {
  const token = useAuthStore((s) => s.token);
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (botId: string) =>
      apiFetch<CompileWikiResponse>(
        API_ENDPOINTS.bots.compileWiki(botId),
        { method: "POST" },
        token ?? undefined,
      ),
    onSuccess: (_data, botId) => {
      toast.success("Wiki 編譯已開始", {
        description: "編譯需要數分鐘，狀態會自動更新。",
      });
      // Invalidate to trigger immediate re-poll showing "compiling" state
      queryClient.invalidateQueries({
        queryKey: queryKeys.wiki.status(botId),
      });
    },
    onError: (error) => {
      const message = error instanceof Error ? error.message : "未知錯誤";
      toast.error("觸發 Wiki 編譯失敗", { description: message });
    },
  });
}
