import { useMutation } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api-client";
import { API_ENDPOINTS } from "@/lib/api-endpoints";
import { useAuthStore } from "@/stores/use-auth-store";
import type { McpDiscoverResponse } from "@/types/mcp";

export function useDiscoverMcpTools() {
  const token = useAuthStore((s) => s.token);

  return useMutation({
    mutationFn: (url: string) =>
      apiFetch<McpDiscoverResponse>(
        API_ENDPOINTS.mcp.discover,
        { method: "POST", body: JSON.stringify({ url }) },
        token ?? undefined,
      ),
  });
}
