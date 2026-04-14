import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api-client";
import { API_ENDPOINTS } from "@/lib/api-endpoints";
import { queryKeys } from "@/hooks/queries/keys";
import { useAuthStore } from "@/stores/use-auth-store";
import type {
  McpRegistration,
  CreateMcpServerRequest,
  UpdateMcpServerRequest,
  DiscoverMcpToolsRequest,
  DiscoverMcpToolsResponse,
  TestConnectionResponse,
} from "@/types/mcp-registry";

export function useMcpRegistry() {
  const token = useAuthStore((s) => s.token);

  return useQuery({
    queryKey: queryKeys.mcpRegistry.all,
    queryFn: () =>
      apiFetch<McpRegistration[]>(
        API_ENDPOINTS.mcpRegistry.list,
        {},
        token ?? undefined,
      ),
    enabled: !!token,
    placeholderData: (prev) => prev,
  });
}

export function useMcpRegistryAccessible(tenantId: string | undefined) {
  const token = useAuthStore((s) => s.token);

  return useQuery({
    queryKey: [...queryKeys.mcpRegistry.all, "accessible", tenantId ?? ""],
    queryFn: () =>
      apiFetch<McpRegistration[]>(
        `${API_ENDPOINTS.mcpRegistry.list}?tenant_id=${tenantId}`,
        {},
        token ?? undefined,
      ),
    enabled: !!token && !!tenantId,
    placeholderData: (prev) => prev,
  });
}

export function useCreateMcpRegistration() {
  const token = useAuthStore((s) => s.token);
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: CreateMcpServerRequest) =>
      apiFetch<McpRegistration>(
        API_ENDPOINTS.mcpRegistry.create,
        { method: "POST", body: JSON.stringify(data) },
        token ?? undefined,
      ),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: queryKeys.mcpRegistry.all,
      });
    },
  });
}

export function useUpdateMcpRegistration() {
  const token = useAuthStore((s) => s.token);
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({
      id,
      data,
    }: {
      id: string;
      data: UpdateMcpServerRequest;
    }) =>
      apiFetch<McpRegistration>(
        API_ENDPOINTS.mcpRegistry.update(id),
        { method: "PUT", body: JSON.stringify(data) },
        token ?? undefined,
      ),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: queryKeys.mcpRegistry.all,
      });
    },
  });
}

export function useDeleteMcpRegistration() {
  const token = useAuthStore((s) => s.token);
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (id: string) =>
      apiFetch<void>(
        API_ENDPOINTS.mcpRegistry.delete(id),
        { method: "DELETE" },
        token ?? undefined,
      ),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: queryKeys.mcpRegistry.all,
      });
    },
  });
}

export function useDiscoverMcpRegistryTools() {
  const token = useAuthStore((s) => s.token);

  return useMutation({
    mutationFn: (data: DiscoverMcpToolsRequest) =>
      apiFetch<DiscoverMcpToolsResponse>(
        API_ENDPOINTS.mcpRegistry.discover,
        { method: "POST", body: JSON.stringify(data) },
        token ?? undefined,
      ),
  });
}

export function useTestMcpConnection() {
  const token = useAuthStore((s) => s.token);

  return useMutation({
    mutationFn: (id: string) =>
      apiFetch<TestConnectionResponse>(
        API_ENDPOINTS.mcpRegistry.testConnection(id),
        { method: "POST" },
        token ?? undefined,
      ),
  });
}
