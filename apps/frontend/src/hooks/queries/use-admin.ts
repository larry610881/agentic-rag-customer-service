import { useQuery } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api-client";
import { API_ENDPOINTS } from "@/lib/api-endpoints";
import { queryKeys } from "@/hooks/queries/keys";
import { useAuthStore } from "@/stores/use-auth-store";
import type { KnowledgeBase } from "@/types/knowledge";
import type { Bot } from "@/types/bot";
import type { PaginatedResponse } from "@/types/api";

/**
 * S-Gov.3: 系統管理區跨租戶總覽改走 /api/v1/admin/* 專屬端點，
 * 與租戶視角的 /api/v1/bots / /api/v1/knowledge-bases 徹底分離，
 * 不再靠 system_admin query param override 混合視角。
 */

export function useAdminKnowledgeBases(tenantId?: string, page = 1, pageSize = 20) {
  const token = useAuthStore((s) => s.token);
  const role = useAuthStore((s) => s.role);

  const params = new URLSearchParams();
  if (tenantId) params.set("tenant_id", tenantId);
  params.set("page", String(page));
  params.set("page_size", String(pageSize));
  const url = `${API_ENDPOINTS.adminKnowledgeBases.list}?${params.toString()}`;

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
  const url = `${API_ENDPOINTS.adminBots.list}?${params.toString()}`;

  return useQuery({
    queryKey: [...queryKeys.admin.bots(tenantId), page, pageSize],
    queryFn: () =>
      apiFetch<PaginatedResponse<Bot>>(url, {}, token ?? undefined),
    enabled: !!token && role === "system_admin",
  });
}
