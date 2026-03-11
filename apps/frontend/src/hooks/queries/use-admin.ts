import { useQuery } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api-client";
import { API_ENDPOINTS } from "@/lib/api-endpoints";
import { queryKeys } from "@/hooks/queries/keys";
import { useAuthStore } from "@/stores/use-auth-store";
import type { KnowledgeBase } from "@/types/knowledge";
import type { Bot } from "@/types/bot";

export function useAdminKnowledgeBases(tenantId?: string) {
  const token = useAuthStore((s) => s.token);
  const role = useAuthStore((s) => s.role);

  const url = tenantId
    ? `${API_ENDPOINTS.knowledgeBases.list}?tenant_id=${tenantId}`
    : API_ENDPOINTS.knowledgeBases.list;

  return useQuery({
    queryKey: queryKeys.admin.knowledgeBases(tenantId),
    queryFn: () =>
      apiFetch<KnowledgeBase[]>(url, {}, token ?? undefined),
    enabled: !!token && role === "system_admin",
  });
}

export function useAdminBots(tenantId?: string) {
  const token = useAuthStore((s) => s.token);
  const role = useAuthStore((s) => s.role);

  const url = tenantId
    ? `${API_ENDPOINTS.bots.list}?tenant_id=${tenantId}`
    : API_ENDPOINTS.bots.list;

  return useQuery({
    queryKey: queryKeys.admin.bots(tenantId),
    queryFn: () =>
      apiFetch<Bot[]>(url, {}, token ?? undefined),
    enabled: !!token && role === "system_admin",
  });
}
