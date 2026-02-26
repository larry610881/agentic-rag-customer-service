"use client";

import { useDocumentChunks } from "@/hooks/queries/use-document-chunks";
import type { ChunkPreviewItem } from "@/types/knowledge";

interface ChunkPreviewPanelProps {
  kbId: string;
  docId: string;
  open: boolean;
}

function chunkBgClass(issues: string[]): string {
  if (issues.includes("too_short")) return "bg-destructive/10";
  if (issues.includes("mid_sentence_break")) return "bg-yellow-100 dark:bg-yellow-900/20";
  return "";
}

function ChunkItem({ chunk }: { chunk: ChunkPreviewItem }) {
  return (
    <div
      className={`rounded border p-3 text-sm ${chunkBgClass(chunk.issues)}`}
      data-testid={`chunk-${chunk.chunk_index}`}
    >
      <div className="mb-1 flex items-center gap-2">
        <span className="font-medium text-muted-foreground">
          #{chunk.chunk_index}
        </span>
        {chunk.issues.map((issue) => (
          <span
            key={issue}
            className="rounded bg-destructive/20 px-1.5 py-0.5 text-xs text-destructive"
            data-testid={`issue-${issue}`}
          >
            {issue === "too_short" ? "過短" : "斷句不完整"}
          </span>
        ))}
      </div>
      <p className="whitespace-pre-wrap break-words">{chunk.content}</p>
    </div>
  );
}

export function ChunkPreviewPanel({ kbId, docId, open }: ChunkPreviewPanelProps) {
  const { data, isLoading } = useDocumentChunks(kbId, docId, open);

  if (!open) return null;

  if (isLoading) {
    return (
      <div className="border-t px-4 py-3 text-sm text-muted-foreground">
        載入分塊預覽...
      </div>
    );
  }

  if (!data || data.chunks.length === 0) {
    return (
      <div className="border-t px-4 py-3 text-sm text-muted-foreground">
        無分塊資料
      </div>
    );
  }

  return (
    <div className="border-t px-4 py-3" data-testid="chunk-preview-panel">
      <p className="mb-2 text-sm text-muted-foreground">
        共 {data.total} 個分塊（顯示前 {data.chunks.length} 個）
      </p>
      <div className="flex flex-col gap-2">
        {data.chunks.map((chunk) => (
          <ChunkItem key={chunk.id} chunk={chunk} />
        ))}
      </div>
    </div>
  );
}
