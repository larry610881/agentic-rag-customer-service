import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api-client";
import { API_ENDPOINTS } from "@/lib/api-endpoints";
import { queryKeys } from "@/hooks/queries/keys";
import { useAuthStore } from "@/stores/use-auth-store";

export interface RateLimitConfig {
  endpoint_group: string;
  requests_per_minute: number;
  burst_size: number;
  per_user_requests_per_minute: number | null;
}

export function useRateLimits(tenantId: string | undefined) {
  const token = useAuthStore((s) => s.token);
  return useQuery({
    queryKey: queryKeys.rateLimits.byTenant(tenantId ?? ""),
    queryFn: () =>
      apiFetch<RateLimitConfig[]>(
        API_ENDPOINTS.rateLimits.byTenant(tenantId!),
        {},
        token ?? undefined,
      ),
    enabled: !!tenantId,
  });
}

export function useUpdateRateLimit(tenantId: string) {
  const token = useAuthStore((s) => s.token);
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: RateLimitConfig) =>
      apiFetch<RateLimitConfig>(
        API_ENDPOINTS.rateLimits.byTenant(tenantId),
        { method: "PUT", body: JSON.stringify(body) },
        token ?? undefined,
      ),
    onSuccess: () => {
      qc.invalidateQueries({
        queryKey: queryKeys.rateLimits.byTenant(tenantId),
      });
    },
  });
}

export function useSystemRateLimits() {
  const token = useAuthStore((s) => s.token);
  return useQuery({
    queryKey: queryKeys.rateLimits.defaults,
    queryFn: () =>
      apiFetch<RateLimitConfig[]>(
        "/api/v1/admin/rate-limits/defaults",
        {},
        token ?? undefined,
      ),
  });
}

export function useUpdateSystemRateLimit() {
  const token = useAuthStore((s) => s.token);
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: RateLimitConfig) =>
      apiFetch<RateLimitConfig>(
        "/api/v1/admin/rate-limits/defaults",
        { method: "PUT", body: JSON.stringify(body) },
        token ?? undefined,
      ),
    onSuccess: () => {
      qc.invalidateQueries({
        queryKey: queryKeys.rateLimits.defaults,
      });
    },
  });
}
