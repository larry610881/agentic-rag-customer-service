import { useQuery } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api-client";
import { API_ENDPOINTS } from "@/lib/api-endpoints";
import { queryKeys } from "@/hooks/queries/keys";
import { useAuthStore } from "@/stores/use-auth-store";
import type { KnowledgeBase } from "@/types/knowledge";
import type { Bot } from "@/types/bot";

export function useAdminKnowledgeBases() {
  const token = useAuthStore((s) => s.token);
  const role = useAuthStore((s) => s.role);

  return useQuery({
    queryKey: queryKeys.admin.knowledgeBases,
    queryFn: () =>
      apiFetch<KnowledgeBase[]>(
        API_ENDPOINTS.knowledgeBases.list,
        {},
        token ?? undefined,
      ),
    enabled: !!token && role === "system_admin",
  });
}

export function useAdminBots() {
  const token = useAuthStore((s) => s.token);
  const role = useAuthStore((s) => s.role);

  return useQuery({
    queryKey: queryKeys.admin.bots,
    queryFn: () =>
      apiFetch<Bot[]>(API_ENDPOINTS.bots.list, {}, token ?? undefined),
    enabled: !!token && role === "system_admin",
  });
}
