import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { apiFetch } from "@/lib/api-client";
import { API_ENDPOINTS } from "@/lib/api-endpoints";
import { queryKeys } from "@/hooks/queries/keys";
import { useAuthStore } from "@/stores/use-auth-store";
import type { KnowledgeBase } from "@/types/knowledge";
import type { PaginatedResponse } from "@/types/api";

export function useKnowledgeBases(page = 1, pageSize = 20) {
  const token = useAuthStore((s) => s.token);
  const tenantId = useAuthStore((s) => s.tenantId);

  return useQuery({
    queryKey: [...queryKeys.knowledgeBases.all(tenantId ?? ""), page, pageSize],
    queryFn: () =>
      apiFetch<PaginatedResponse<KnowledgeBase>>(
        `${API_ENDPOINTS.knowledgeBases.list}?page=${page}&page_size=${pageSize}`,
        {},
        token ?? undefined,
      ),
    enabled: !!token && !!tenantId,
  });
}

/** 單 KB 詳情（KB Studio 設定 tab 用）— admin 可看任意租戶 KB（後端 ensure_kb_accessible bypass）。 */
export function useKnowledgeBase(kbId: string) {
  const token = useAuthStore((s) => s.token);
  return useQuery({
    queryKey: ["knowledge-bases", "detail", kbId] as const,
    queryFn: () =>
      apiFetch<KnowledgeBase>(
        API_ENDPOINTS.knowledgeBases.update(kbId), // GET /knowledge-bases/:id 共用 path
        {},
        token ?? undefined,
      ),
    enabled: !!token && !!kbId,
  });
}

export function useCreateKnowledgeBase() {
  const token = useAuthStore((s) => s.token);
  const tenantId = useAuthStore((s) => s.tenantId);
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: {
      name: string;
      description: string;
      ocr_mode?: string;
      ocr_model?: string;
      context_model?: string;
      classification_model?: string;
    }) =>
      apiFetch<KnowledgeBase>(
        API_ENDPOINTS.knowledgeBases.create,
        { method: "POST", body: JSON.stringify(data) },
        token ?? undefined,
      ),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: queryKeys.knowledgeBases.all(tenantId ?? ""),
      });
    },
  });
}

export function useUpdateKnowledgeBase() {
  const token = useAuthStore((s) => s.token);
  const tenantId = useAuthStore((s) => s.tenantId);
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({
      kbId,
      data,
    }: {
      kbId: string;
      data: Partial<Omit<KnowledgeBase, "id" | "tenant_id" | "document_count" | "created_at" | "updated_at">>;
    }) =>
      apiFetch<KnowledgeBase>(
        API_ENDPOINTS.knowledgeBases.update(kbId),
        { method: "PATCH", body: JSON.stringify(data) },
        token ?? undefined,
      ),
    onSuccess: (_data, vars) => {
      queryClient.invalidateQueries({
        queryKey: queryKeys.knowledgeBases.all(tenantId ?? ""),
      });
      // KB Studio 設定 tab 也要 refresh
      queryClient.invalidateQueries({
        queryKey: ["knowledge-bases", "detail", vars.kbId] as const,
      });
      toast.success("知識庫設定已更新");
    },
    onError: () => {
      toast.error("更新知識庫設定失敗");
    },
  });
}

export function useDeleteKnowledgeBase() {
  const token = useAuthStore((s) => s.token);
  const tenantId = useAuthStore((s) => s.tenantId);
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (kbId: string) =>
      apiFetch<void>(
        API_ENDPOINTS.knowledgeBases.delete(kbId),
        { method: "DELETE" },
        token ?? undefined,
      ),
    onSuccess: () => {
      toast.success("知識庫已刪除");
      queryClient.invalidateQueries({
        queryKey: queryKeys.knowledgeBases.all(tenantId ?? ""),
      });
    },
    onError: () => {
      toast.error("刪除知識庫失敗");
    },
  });
}
