import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { apiFetch } from "@/lib/api-client";
import { API_ENDPOINTS } from "@/lib/api-endpoints";
import { useAuthStore } from "@/stores/use-auth-store";

export interface AdminTool {
  name: string;
  label: string;
  description: string;
  requires_kb: boolean;
  scope: "global" | "tenant";
  tenant_ids: string[];
}

export interface UpdateToolScopePayload {
  scope: "global" | "tenant";
  tenant_ids: string[];
}

const ADMIN_TOOLS_KEY = ["admin-tools"] as const;

/** 系統管理員用：列出所有 built-in tool（含 scope + 白名單） */
export function useAdminTools() {
  const token = useAuthStore((s) => s.token);

  return useQuery({
    queryKey: ADMIN_TOOLS_KEY,
    queryFn: () =>
      apiFetch<AdminTool[]>(
        API_ENDPOINTS.adminTools.list,
        {},
        token ?? undefined,
      ),
    enabled: !!token,
  });
}

/** 系統管理員用：更新工具的 scope 與白名單 */
export function useUpdateToolScope() {
  const token = useAuthStore((s) => s.token);
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({
      name,
      payload,
    }: {
      name: string;
      payload: UpdateToolScopePayload;
    }) =>
      apiFetch<AdminTool>(
        API_ENDPOINTS.adminTools.update(name),
        { method: "PUT", body: JSON.stringify(payload) },
        token ?? undefined,
      ),
    onSuccess: () => {
      // Refresh both admin list and tenant-facing list
      queryClient.invalidateQueries({ queryKey: ADMIN_TOOLS_KEY });
      queryClient.invalidateQueries({ queryKey: ["built-in-tools"] });
    },
  });
}
