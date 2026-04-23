import { useEffect, useRef, useState } from "react";
import { RotateCcw, Trash2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { ChunkCard } from "@/features/knowledge/components/chunk-card";
import {
  useDeleteChunk,
  useReembedChunk,
  useUpdateChunk,
} from "@/hooks/queries/use-kb-chunks";
import type { Chunk } from "@/types/chunk";
import { ConfirmDangerDialog } from "@/components/ui/confirm-danger-dialog";

interface ChunkEditorProps {
  chunk: Chunk;
  kbId: string;
  categoryName?: string;
}

const AUTOSAVE_DEBOUNCE_MS = 1000;

export function ChunkEditor({ chunk, kbId, categoryName }: ChunkEditorProps) {
  const [draft, setDraft] = useState(chunk.content);
  const [savedDraft, setSavedDraft] = useState(chunk.content);
  const [status, setStatus] = useState<"idle" | "saving" | "saved" | "error">(
    "idle",
  );
  const [confirmOpen, setConfirmOpen] = useState(false);
  const debounceRef = useRef<number | null>(null);

  const updateMutation = useUpdateChunk(kbId);
  const reembedMutation = useReembedChunk();
  const deleteMutation = useDeleteChunk(kbId);

  useEffect(() => {
    setDraft(chunk.content);
    setSavedDraft(chunk.content);
    setStatus("idle");
  }, [chunk.id, chunk.content]);

  useEffect(() => {
    if (draft === savedDraft) return;
    setStatus("saving");
    if (debounceRef.current) window.clearTimeout(debounceRef.current);
    debounceRef.current = window.setTimeout(() => {
      updateMutation.mutate(
        { docId: chunk.document_id, chunkId: chunk.id, body: { content: draft } },
        {
          onSuccess: () => {
            setSavedDraft(draft);
            setStatus("saved");
          },
          onError: () => setStatus("error"),
        },
      );
    }, AUTOSAVE_DEBOUNCE_MS);
    return () => {
      if (debounceRef.current) window.clearTimeout(debounceRef.current);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [draft]);

  const handleReembed = () => {
    reembedMutation.mutate(chunk.id);
  };

  const handleDelete = () => {
    deleteMutation.mutate(chunk.id, {
      onSuccess: () => setConfirmOpen(false),
    });
  };

  const statusLabel = {
    idle: "",
    saving: "儲存中...",
    saved: "✓ 已儲存 + re-embedding",
    error: "✗ 儲存失敗",
  }[status];

  return (
    <ChunkCard chunk={chunk} mode="edit" categoryName={categoryName}>
      <Textarea
        value={draft}
        onChange={(e) => setDraft(e.target.value)}
        rows={Math.min(Math.max(draft.split("\n").length, 3), 8)}
        className="text-sm font-mono"
      />
      <div className="mt-2 flex items-center justify-between text-xs">
        <span
          className={
            status === "error"
              ? "text-destructive"
              : status === "saved"
              ? "text-emerald-600"
              : "text-muted-foreground"
          }
        >
          {statusLabel}
        </span>
        <div className="flex gap-1">
          <Button
            size="sm"
            variant="ghost"
            onClick={handleReembed}
            disabled={reembedMutation.isPending}
            title="重新向量化"
          >
            <RotateCcw className="h-3 w-3 mr-1" />
            re-embed
          </Button>
          <Button
            size="sm"
            variant="ghost"
            onClick={() => setConfirmOpen(true)}
            disabled={deleteMutation.isPending}
            title="刪除 chunk"
            className="text-destructive hover:text-destructive"
          >
            <Trash2 className="h-3 w-3" />
          </Button>
        </div>
      </div>
      <ConfirmDangerDialog
        open={confirmOpen}
        onOpenChange={setConfirmOpen}
        title="確認刪除 chunk？"
        description={`此操作不可復原，會從 DB 與 Milvus 刪除 chunk #${chunk.chunk_index}。`}
        isPending={deleteMutation.isPending}
        onConfirm={handleDelete}
      />
    </ChunkCard>
  );
}
