import { useQuery } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api-client";
import { API_ENDPOINTS } from "@/lib/api-endpoints";
import { queryKeys } from "@/hooks/queries/keys";
import { useAuthStore } from "@/stores/use-auth-store";
import type { KnowledgeBase } from "@/types/knowledge";
import type { Bot } from "@/types/bot";
import type { PaginatedResponse } from "@/types/api";

export function useAdminKnowledgeBases(tenantId?: string, page = 1, pageSize = 20) {
  const token = useAuthStore((s) => s.token);
  const role = useAuthStore((s) => s.role);

  const params = new URLSearchParams();
  if (tenantId) params.set("tenant_id", tenantId);
  params.set("page", String(page));
  params.set("page_size", String(pageSize));
  const url = `${API_ENDPOINTS.knowledgeBases.list}?${params.toString()}`;

  return useQuery({
    queryKey: [...queryKeys.admin.knowledgeBases(tenantId), page, pageSize],
    queryFn: () =>
      apiFetch<PaginatedResponse<KnowledgeBase>>(url, {}, token ?? undefined),
    enabled: !!token && role === "system_admin",
  });
}

export function useAdminBots(tenantId?: string, page = 1, pageSize = 20) {
  const token = useAuthStore((s) => s.token);
  const role = useAuthStore((s) => s.role);

  const params = new URLSearchParams();
  if (tenantId) params.set("tenant_id", tenantId);
  params.set("page", String(page));
  params.set("page_size", String(pageSize));
  const url = `${API_ENDPOINTS.bots.list}?${params.toString()}`;

  return useQuery({
    queryKey: [...queryKeys.admin.bots(tenantId), page, pageSize],
    queryFn: () =>
      apiFetch<PaginatedResponse<Bot>>(url, {}, token ?? undefined),
    enabled: !!token && role === "system_admin",
  });
}
