import { useDocumentChunks } from "@/hooks/queries/use-document-chunks";
import type { ChunkPreviewItem } from "@/types/knowledge";
import type { Chunk } from "@/types/chunk";
import { ChunkEditor } from "@/features/admin/kb-studio/chunk-editor";

interface ChunkPreviewPanelProps {
  kbId: string;
  docId: string;
  open: boolean;
  /**
   * 啟用 drill-down 編輯模式（admin 用）。
   * 每個 chunk 顯示 ChunkEditor — 可改 content / context / 刪除 / re-embed。
   * 預設 false（唯讀，租戶端使用）。
   */
  editable?: boolean;
}

function chunkBgClass(issues: string[]): string {
  if (issues.includes("too_short")) return "bg-destructive/10";
  if (issues.includes("mid_sentence_break"))
    return "bg-yellow-100 dark:bg-yellow-900/20";
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

/**
 * preview-only ChunkPreviewItem (簡化版) → admin 編輯所需的完整 Chunk 型別。
 * tenant_id / category_id / quality_flag preview 沒帶，這裡用 reasonable defaults：
 *  - tenant_id: 編輯時不會用到（後端從 token 取）
 *  - category_id: null（編輯 dialog 暫不顯示分類，不影響編輯）
 *  - quality_flag: 從 issues[0] 推導（issues=[] 時 null）
 */
function toEditableChunk(p: ChunkPreviewItem, fallbackDocId: string): Chunk {
  return {
    id: p.id,
    document_id: p.document_id ?? fallbackDocId,
    tenant_id: "",
    content: p.content,
    context_text: p.context_text ?? "",
    chunk_index: p.chunk_index,
    category_id: null,
    quality_flag: p.issues?.[0] ?? null,
  };
}

export function ChunkPreviewPanel({
  kbId,
  docId,
  open,
  editable = false,
}: ChunkPreviewPanelProps) {
  const { data, isLoading } = useDocumentChunks(kbId, docId, open);

  if (!open) return null;

  if (isLoading) {
    return (
      <div className="px-4 py-3 text-sm text-muted-foreground">
        載入分塊預覽...
      </div>
    );
  }

  if (!data || data.chunks.length === 0) {
    return (
      <div className="px-4 py-3 text-sm text-muted-foreground">
        無分塊資料
      </div>
    );
  }

  return (
    <div className="px-4 py-3" data-testid="chunk-preview-panel">
      <p className="mb-2 text-sm text-muted-foreground">
        共 {data.total} 個分塊（顯示前 {data.chunks.length} 個）
        {editable && (
          <span className="ml-2 text-emerald-600">· 編輯模式</span>
        )}
      </p>
      <div className="flex flex-col gap-2">
        {data.chunks.map((chunk) =>
          editable ? (
            <ChunkEditor
              key={chunk.id}
              chunk={toEditableChunk(chunk, docId)}
              kbId={kbId}
            />
          ) : (
            <ChunkItem key={chunk.id} chunk={chunk} />
          ),
        )}
      </div>
    </div>
  );
}
