/** Issue #67 P2 — 租戶 API 金鑰管理 hooks */
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api-client";
import { API_ENDPOINTS } from "@/lib/api-endpoints";
import { queryKeys } from "@/hooks/queries/keys";
import { useAuthStore } from "@/stores/use-auth-store";
import type { ApiKey, ApiKeyCreated, CreateApiKeyRequest } from "@/types/api-key";
import type { Bot } from "@/types/bot";
import type { PaginatedResponse } from "@/types/api";

/**
 * 列出 API 金鑰。
 * tenant_admin：後端只回自己租戶（tenantId 參數忽略）；
 * system_admin：不帶 tenantId 回全部，帶則過濾該租戶。
 */
export function useApiKeys(tenantId?: string) {
  const token = useAuthStore((s) => s.token);
  const url = tenantId
    ? `${API_ENDPOINTS.apiKeys.list}?tenant_id=${encodeURIComponent(tenantId)}`
    : API_ENDPOINTS.apiKeys.list;

  return useQuery({
    queryKey: queryKeys.apiKeys.all(tenantId),
    queryFn: () => apiFetch<ApiKey[]>(url, {}, token ?? undefined),
    enabled: !!token,
  });
}

export function useApiKeyScopes() {
  const token = useAuthStore((s) => s.token);

  return useQuery({
    queryKey: queryKeys.apiKeys.scopes,
    queryFn: () =>
      apiFetch<string[]>(API_ENDPOINTS.apiKeys.scopes, {}, token ?? undefined),
    enabled: !!token,
    staleTime: 5 * 60 * 1000,
  });
}

export function useCreateApiKey() {
  const token = useAuthStore((s) => s.token);
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: CreateApiKeyRequest) =>
      apiFetch<ApiKeyCreated>(
        API_ENDPOINTS.apiKeys.create,
        { method: "POST", body: JSON.stringify(data) },
        token ?? undefined,
      ),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["api-keys"] });
    },
  });
}

export function useRevokeApiKey() {
  const token = useAuthStore((s) => s.token);
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (id: string) =>
      apiFetch<ApiKey>(
        API_ENDPOINTS.apiKeys.revoke(id),
        { method: "DELETE" },
        token ?? undefined,
      ),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["api-keys"] });
    },
  });
}

/**
 * 建立金鑰時「允許的機器人」候選清單。
 * tenant_admin 走 /bots（自己租戶）；system_admin 的 JWT tenant 是 SYSTEM_TENANT，
 * /bots 通常 0 筆，改走 /admin/bots?tenant_id= 取目標租戶的機器人。
 */
export function useApiKeyBotOptions(tenantId?: string) {
  const token = useAuthStore((s) => s.token);
  const role = useAuthStore((s) => s.role);
  const isSystemAdmin = role === "system_admin";

  const url = isSystemAdmin
    ? `${API_ENDPOINTS.adminBots.list}?tenant_id=${encodeURIComponent(tenantId ?? "")}&page=1&page_size=200`
    : `${API_ENDPOINTS.bots.list}?page=1&page_size=100`;

  return useQuery({
    queryKey: queryKeys.apiKeys.botOptions(isSystemAdmin ? tenantId : undefined),
    queryFn: () =>
      apiFetch<PaginatedResponse<Bot>>(url, {}, token ?? undefined),
    enabled: !!token && (!isSystemAdmin || !!tenantId),
    select: (data) => data.items,
  });
}
