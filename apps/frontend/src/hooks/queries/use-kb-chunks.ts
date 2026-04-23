import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api-client";
import { API_ENDPOINTS } from "@/lib/api-endpoints";
import { queryKeys } from "@/hooks/queries/keys";
import { useAuthStore } from "@/stores/use-auth-store";
import type {
  Chunk,
  ChunkListResponse,
  KbQualitySummary,
  RetrievalTestRequest,
  RetrievalTestResult,
  UpdateChunkRequest,
} from "@/types/chunk";

interface ListParams {
  kbId: string;
  page?: number;
  pageSize?: number;
  categoryId?: string;
}

export function useKbChunks({
  kbId,
  page = 1,
  pageSize = 50,
  categoryId,
}: ListParams) {
  const token = useAuthStore((s) => s.token);
  return useQuery({
    queryKey: queryKeys.kbStudio.chunks(kbId, page, pageSize, categoryId),
    queryFn: () =>
      apiFetch<ChunkListResponse>(
        API_ENDPOINTS.adminChunks.list(kbId, page, pageSize, categoryId),
        {},
        token ?? undefined,
      ),
    enabled: !!token && !!kbId,
  });
}

export function useUpdateChunk(kbId: string) {
  const token = useAuthStore((s) => s.token);
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({
      docId,
      chunkId,
      body,
    }: {
      docId: string;
      chunkId: string;
      body: UpdateChunkRequest;
    }) =>
      apiFetch<{ status: string; chunk_id: string }>(
        API_ENDPOINTS.adminChunks.update(docId, chunkId),
        { method: "PATCH", body: JSON.stringify(body) },
        token ?? undefined,
      ),
    onSuccess: () => {
      qc.invalidateQueries({
        queryKey: ["kb-studio", "chunks", kbId] as const,
      });
    },
  });
}

export function useDeleteChunk(kbId: string) {
  const token = useAuthStore((s) => s.token);
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (chunkId: string) =>
      apiFetch<void>(
        API_ENDPOINTS.adminChunks.delete(chunkId),
        { method: "DELETE" },
        token ?? undefined,
      ),
    onSuccess: () => {
      qc.invalidateQueries({
        queryKey: ["kb-studio", "chunks", kbId] as const,
      });
    },
  });
}

export function useReembedChunk() {
  const token = useAuthStore((s) => s.token);
  return useMutation({
    mutationFn: (chunkId: string) =>
      apiFetch<{ status: string; job_id?: string }>(
        API_ENDPOINTS.adminChunks.reembed(chunkId),
        { method: "POST" },
        token ?? undefined,
      ),
  });
}

export function useRetrievalTest(kbId: string) {
  const token = useAuthStore((s) => s.token);
  return useMutation({
    mutationFn: (body: RetrievalTestRequest) =>
      apiFetch<RetrievalTestResult>(
        API_ENDPOINTS.adminChunks.retrievalTest(kbId),
        { method: "POST", body: JSON.stringify(body) },
        token ?? undefined,
      ),
  });
}

export function useKbQualitySummary(kbId: string) {
  const token = useAuthStore((s) => s.token);
  return useQuery({
    queryKey: queryKeys.kbStudio.qualitySummary(kbId),
    queryFn: () =>
      apiFetch<KbQualitySummary>(
        API_ENDPOINTS.adminChunks.qualitySummary(kbId),
        {},
        token ?? undefined,
      ),
    enabled: !!token && !!kbId,
  });
}

export type { Chunk };
