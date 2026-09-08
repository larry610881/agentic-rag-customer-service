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
    // 被限流時不要繼續每 3 秒敲一次——輪詢本身就是把租戶額度吃光的元凶之一
    // （批次上傳 33 檔時同時有 request/confirm 在打）。改依 Retry-After 退避。
    retry: (failureCount, error) =>
      error instanceof ApiError && error.status === 429
        ? false
        : failureCount < 2,
    refetchInterval: (query) => {
      const error = query.state.error;
      if (error instanceof ApiError && error.status === 429) {
        return Math.max(5, error.retryAfter ?? 30) * 1000;
      }
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
      // Invalidate categories immediately + delayed refresh for classify_kb result
      queryClient.invalidateQueries({ queryKey: ["categories", variables.knowledgeBaseId] });
      setTimeout(() => {
        queryClient.invalidateQueries({ queryKey: ["categories", variables.knowledgeBaseId] });
      }, 5000);
      setTimeout(() => {
        queryClient.invalidateQueries({ queryKey: ["categories", variables.knowledgeBaseId] });
      }, 15000);
    },
  });
}

interface RequestUploadResponse {
  document_id: string;
  task_id: string;
  upload_url: string;
  storage_path: string;
}

/**
 * 單一檔案跨重試共享的上傳進度（Issue #88）。
 *
 * 注意簽名網址效期 600 秒：重試在限流暫停下最多累積數分鐘，仍在效期內。
 * 若真的過期，PUT 會回 403 → 該檔顯示為失敗（真實錯誤），而不是再建一列文件。
 */
export type UploadResumeState = {
  request?: RequestUploadResponse;
  gcsUploaded?: boolean;
};

export function useUploadDocument() {
  const token = useAuthStore((s) => s.token);
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (data: {
      knowledgeBaseId: string;
      file: File;
      onProgress?: (pct: number) => void;
      /**
       * 同一個檔重試時傳入同一個物件，用來記住已完成的步驟。
       *
       * 為什麼必要：上傳是三步（request-upload 建立文件列 → 直傳 GCS →
       * confirm-upload 派工）。原本重試的粒度是整個 mutation，於是 429 打在
       * 第三步時，重試會從第一步重跑並**建立第二列 document**；第一列永遠等不到
       * confirm-upload，就成了永遠「等待中」的孤兒（Issue #88，2026-09-08 實測
       * 產生 3 筆）。帶著 resume 重試就只補做失敗的那一步。
       */
      resume?: UploadResumeState;
    }): Promise<UploadDocumentResponse> => {
      const resume = data.resume ?? {};

      // Step 1: Request signed upload URL from backend（已做過就沿用）
      let reqRes = resume.request;
      if (!reqRes) {
        console.log("[upload] Step 1: requesting signed URL...");
        reqRes = await apiFetch<RequestUploadResponse>(
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
        resume.request = reqRes;
        console.log("[upload] Step 1 OK:", reqRes.document_id, "url_len:", reqRes.upload_url?.length);
      } else {
        console.log("[upload] Step 1 skipped (resume):", reqRes.document_id);
      }

      // Step 2: Direct upload to GCS via signed URL (bypass Cloud Run)
      if (reqRes.upload_url && resume.gcsUploaded) {
        console.log("[upload] Step 2 skipped (resume)");
        data.onProgress?.(100);
      } else if (reqRes.upload_url) {
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
        resume.gcsUploaded = true;
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
      // Invalidate categories after batch delete (classify_kb re-runs)
      queryClient.invalidateQueries({ queryKey: ["categories", variables.knowledgeBaseId] });
      setTimeout(() => {
        queryClient.invalidateQueries({ queryKey: ["categories", variables.knowledgeBaseId] });
      }, 5000);
      setTimeout(() => {
        queryClient.invalidateQueries({ queryKey: ["categories", variables.knowledgeBaseId] });
      }, 15000);
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
        ocr_mode?: string;
        ocr_model?: string;
        context_model?: string;
        ocr_slice_grid?: string;
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
      // 父文件列表
      queryClient.invalidateQueries({
        queryKey: queryKeys.documents.all(variables.knowledgeBaseId),
      });
      // 子頁列表（PDF 子頁 reprocess 時 UI 才會立即從 failed → processing）
      // ChildrenRows 用 ["document-children", kbId, parentId] 當 key — prefix invalidate 全部
      queryClient.invalidateQueries({
        queryKey: ["document-children", variables.knowledgeBaseId],
      });
    },
  });
}
