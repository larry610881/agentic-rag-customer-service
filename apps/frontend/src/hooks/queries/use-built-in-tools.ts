import { useQuery } from "@tanstack/react-query";

import { apiFetch } from "@/lib/api-client";
import { useAuthStore } from "@/stores/use-auth-store";

export interface BuiltInTool {
  name: string;
  label: string;
  description: string;
  requires_kb: boolean;
}

/**
 * 取系統內建可啟用 tools 清單，供 bot 編輯頁顯示多選 checkbox。
 * Metadata 幾乎不變，cache 永久（重整頁才會重 fetch）。
 */
export function useBuiltInTools() {
  const token = useAuthStore((s) => s.token);

  return useQuery({
    queryKey: ["built-in-tools"],
    queryFn: () =>
      apiFetch<BuiltInTool[]>(
        "/api/v1/agent/built-in-tools",
        {},
        token ?? undefined,
      ),
    enabled: !!token,
    staleTime: Infinity,
  });
}
