import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api-client";
import { API_ENDPOINTS } from "@/lib/api-endpoints";
import { queryKeys } from "@/hooks/queries/keys";
import { useAuthStore } from "@/stores/use-auth-store";
import type { Tenant } from "@/types/auth";
import type { PaginatedResponse } from "@/types/api";

export function useTenants(page = 1, pageSize = 20) {
  const token = useAuthStore((s) => s.token);

  return useQuery({
    queryKey: [...queryKeys.tenants.all, page, pageSize],
    queryFn: () =>
      apiFetch<PaginatedResponse<Tenant>>(
        `${API_ENDPOINTS.tenants.list}?page=${page}&page_size=${pageSize}`,
        {},
        token ?? undefined,
      ),
    enabled: !!token,
  });
}

export function useCreateTenant() {
  const token = useAuthStore((s) => s.token);
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: { name: string; slug: string }) =>
      apiFetch<Tenant>(
        API_ENDPOINTS.tenants.create,
        { method: "POST", body: JSON.stringify(data) },
        token ?? undefined,
      ),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.tenants.all });
    },
  });
}
