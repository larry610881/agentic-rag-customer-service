import { useMutation } from "@tanstack/react-query";
import { ApiError } from "@/lib/api-client";
import { API_ENDPOINTS } from "@/lib/api-endpoints";
import { useAuthStore } from "@/stores/use-auth-store";
import type { UploadDocumentResponse } from "@/types/knowledge";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export function useUploadDocument() {
  const token = useAuthStore((s) => s.token);

  return useMutation({
    mutationFn: async (data: {
      knowledgeBaseId: string;
      file: File;
    }): Promise<UploadDocumentResponse> => {
      const formData = new FormData();
      formData.append("file", data.file);

      const res = await fetch(`${API_BASE}${API_ENDPOINTS.documents.upload(data.knowledgeBaseId)}`, {
        method: "POST",
        headers: {
          Authorization: `Bearer ${token}`,
        },
        body: formData,
      });

      if (!res.ok) {
        const body = await res.text();
        throw new ApiError(res.status, body);
      }

      return res.json() as Promise<UploadDocumentResponse>;
    },
  });
}
