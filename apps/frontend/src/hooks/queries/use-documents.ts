import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ApiError, apiFetch } from "@/lib/api-client";
import { API_ENDPOINTS } from "@/lib/api-endpoints";
import { queryKeys } from "@/hooks/queries/keys";
import { useAuthStore } from "@/stores/use-auth-store";
import type {
  BatchDeleteResult,
  BatchReprocessResult,
  DocumentResponse,
  UploadDocumentResponse,
} from "@/types/knowledge";
import type { PaginatedResponse } from "@/types/api";
import { API_BASE } from "@/lib/api-config";

export function useDocuments(kbId: string, page = 1, pageSize = 20) {
  const token = useAuthStore((s) => s.token);

  return useQuery({
    queryKey: [...queryKeys.documents.all(kbId), page, pageSize],
    queryFn: () =>
      apiFetch<PaginatedResponse<DocumentResponse>>(
        `${API_ENDPOINTS.documents.list(kbId)}?page=${page}&page_size=${pageSize}`,
        {},
        token ?? undefined,
      ),
    enabled: !!kbId && !!token,
    refetchInterval: (query) => {
      const data = query.state.data;
      if (data?.items?.some((d) => d.status === "pending" || d.status === "processing")) {
        return 3000;
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

interface RequestUploadResponse {
  document_id: string;
  task_id: string;
  upload_url: string;
  storage_path: string;
}

export function useUploadDocument() {
  const token = useAuthStore((s) => s.token);
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (data: {
      knowledgeBaseId: string;
      file: File;
      onProgress?: (pct: number) => void;
    }): Promise<UploadDocumentResponse> => {
      // Step 1: Request signed upload URL from backend
      console.log("[upload] Step 1: requesting signed URL...");
      const reqRes = await apiFetch<RequestUploadResponse>(
        API_ENDPOINTS.documents.requestUpload(data.knowledgeBaseId),
        {
          method: "POST",
          body: JSON.stringify({
            filename: data.file.name,
            content_type: data.file.type || "application/octet-stream",
          }),
        },
        token ?? undefined,
      );
      console.log("[upload] Step 1 OK:", reqRes.document_id, "url_len:", reqRes.upload_url?.length);

      // Step 2: Direct upload to GCS via signed URL (bypass Cloud Run)
      if (reqRes.upload_url) {
        console.log("[upload] Step 2: uploading to GCS...");
        await new Promise<void>((resolve, reject) => {
          const xhr = new XMLHttpRequest();
          xhr.open("PUT", reqRes.upload_url, true);
          xhr.setRequestHeader(
            "Content-Type",
            data.file.type || "application/octet-stream",
          );
          xhr.upload.onprogress = (e) => {
            if (e.lengthComputable) {
              const pct = Math.round((e.loaded / e.total) * 100);
              console.log(`[upload] GCS progress: ${pct}%`);
              data.onProgress?.(pct);
            }
          };
          xhr.onload = () => {
            console.log("[upload] GCS response:", xhr.status, xhr.statusText);
            xhr.status >= 200 && xhr.status < 300
              ? resolve()
              : reject(new Error(`GCS upload failed: ${xhr.status} ${xhr.responseText?.substring(0, 200)}`));
          };
          xhr.onerror = () => {
            console.error("[upload] GCS network error");
            reject(new Error("GCS upload network error"));
          };
          xhr.send(data.file);
        });
        console.log("[upload] Step 2 OK");
      } else {
        // Fallback: old multipart upload (local storage)
        const formData = new FormData();
        formData.append("file", data.file);
        const res = await fetch(
          `${API_BASE}${API_ENDPOINTS.documents.upload(data.knowledgeBaseId)}`,
          {
            method: "POST",
            headers: { Authorization: `Bearer ${token}` },
            body: formData,
          },
        );
        if (!res.ok) throw new ApiError(res.status, await res.text());
        return res.json() as Promise<UploadDocumentResponse>;
      }

      // Step 3: Confirm upload, trigger processing
      // Re-fetch token — GCS upload may have taken minutes, original token expired
      const freshToken = useAuthStore.getState().token;
      console.log("[upload] Step 3: confirming...");
      return apiFetch<UploadDocumentResponse>(
        API_ENDPOINTS.documents.confirmUpload(data.knowledgeBaseId),
        {
          method: "POST",
          body: JSON.stringify({
            document_id: reqRes.document_id,
            task_id: reqRes.task_id,
          }),
        },
        freshToken ?? undefined,
      );
    },
    onSuccess: (_data, variables) => {
      queryClient.invalidateQueries({
        queryKey: queryKeys.documents.all(variables.knowledgeBaseId),
      });
    },
  });
}

export function useBatchDeleteDocuments() {
  const token = useAuthStore((s) => s.token);
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (data: {
      knowledgeBaseId: string;
      docIds: string[];
    }): Promise<BatchDeleteResult> => {
      return apiFetch<BatchDeleteResult>(
        API_ENDPOINTS.documents.batchDelete(data.knowledgeBaseId),
        {
          method: "POST",
          body: JSON.stringify({ doc_ids: data.docIds }),
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

export function useBatchReprocessDocuments() {
  const token = useAuthStore((s) => s.token);
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (data: {
      knowledgeBaseId: string;
      docIds: string[];
    }): Promise<BatchReprocessResult> => {
      return apiFetch<BatchReprocessResult>(
        API_ENDPOINTS.documents.batchReprocess(data.knowledgeBaseId),
        {
          method: "POST",
          body: JSON.stringify({ doc_ids: data.docIds }),
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
