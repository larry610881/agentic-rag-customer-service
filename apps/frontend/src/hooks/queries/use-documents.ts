import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ApiError, apiFetch } from "@/lib/api-client";
import { API_ENDPOINTS } from "@/lib/api-endpoints";
import { queryKeys } from "@/hooks/queries/keys";
import { useAuthStore } from "@/stores/use-auth-store";
import type { DocumentResponse, UploadDocumentResponse } from "@/types/knowledge";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export function useDocuments(kbId: string) {
  const token = useAuthStore((s) => s.token);

  return useQuery({
    queryKey: queryKeys.documents.all(kbId),
    queryFn: () =>
      apiFetch<DocumentResponse[]>(
        API_ENDPOINTS.documents.list(kbId),
        {},
        token ?? undefined,
      ),
    enabled: !!kbId && !!token,
    refetchInterval: (query) => {
      const data = query.state.data;
      if (data?.some((d) => d.status === "pending" || d.status === "processing")) {
        return 5000;
      }
      return false;
    },
  });
}

export function useDeleteDocument() {
  const token = useAuthStore((s) => s.token);
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (data: {
      knowledgeBaseId: string;
      docId: string;
    }): Promise<void> => {
      const res = await fetch(
        `${API_BASE}${API_ENDPOINTS.documents.delete(data.knowledgeBaseId, data.docId)}`,
        {
          method: "DELETE",
          headers: {
            Authorization: `Bearer ${token}`,
          },
        },
      );

      if (!res.ok) {
        const body = await res.text();
        throw new ApiError(res.status, body);
      }
    },
    onSuccess: (_data, variables) => {
      queryClient.invalidateQueries({
        queryKey: queryKeys.documents.all(variables.knowledgeBaseId),
      });
    },
  });
}

export function useUploadDocument() {
  const token = useAuthStore((s) => s.token);
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (data: {
      knowledgeBaseId: string;
      file: File;
    }): Promise<UploadDocumentResponse> => {
      const formData = new FormData();
      formData.append("file", data.file);

      const res = await fetch(
        `${API_BASE}${API_ENDPOINTS.documents.upload(data.knowledgeBaseId)}`,
        {
          method: "POST",
          headers: {
            Authorization: `Bearer ${token}`,
          },
          body: formData,
        },
      );

      if (!res.ok) {
        const body = await res.text();
        throw new ApiError(res.status, body);
      }

      return res.json() as Promise<UploadDocumentResponse>;
    },
    onSuccess: (_data, variables) => {
      queryClient.invalidateQueries({
        queryKey: queryKeys.documents.all(variables.knowledgeBaseId),
      });
    },
  });
}

export function useReprocessDocument() {
  const token = useAuthStore((s) => s.token);
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (data: {
      knowledgeBaseId: string;
      docId: string;
      params: {
        chunk_size?: number;
        chunk_overlap?: number;
        chunk_strategy?: string;
      };
    }) => {
      return apiFetch(
        API_ENDPOINTS.documents.reprocess(data.knowledgeBaseId, data.docId),
        {
          method: "POST",
          body: JSON.stringify(data.params),
        },
        token ?? undefined,
      );
    },
    onSuccess: (_data, variables) => {
      queryClient.invalidateQueries({
        queryKey: queryKeys.documents.all(variables.knowledgeBaseId),
      });
    },
  });
}
