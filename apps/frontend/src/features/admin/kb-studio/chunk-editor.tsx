import { useEffect, useRef, useState } from "react";
import { RotateCcw, Trash2, Sparkles } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import { ChunkCard } from "@/features/knowledge/components/chunk-card";
import {
  useDeleteChunk,
  useReembedChunk,
  useUpdateChunk,
} from "@/hooks/queries/use-kb-chunks";
import type { Chunk, UpdateChunkRequest } from "@/types/chunk";
import { ConfirmDangerDialog } from "@/components/ui/confirm-danger-dialog";

interface ChunkEditorProps {
  chunk: Chunk;
  kbId: string;
  categoryName?: string;
}

const AUTOSAVE_DEBOUNCE_MS = 1000;

export function ChunkEditor({ chunk, kbId, categoryName }: ChunkEditorProps) {
  const [contentDraft, setContentDraft] = useState(chunk.content);
  const [contextDraft, setContextDraft] = useState(chunk.context_text ?? "");
  const [savedContent, setSavedContent] = useState(chunk.content);
  const [savedContext, setSavedContext] = useState(chunk.context_text ?? "");
  const [status, setStatus] = useState<"idle" | "saving" | "saved" | "error">(
    "idle",
  );
  const [confirmOpen, setConfirmOpen] = useState(false);
  const debounceRef = useRef<number | null>(null);

  const updateMutation = useUpdateChunk(kbId);
  const reembedMutation = useReembedChunk();
  const deleteMutation = useDeleteChunk(kbId);

  // Reset local state when chunk id changes (不同 chunk row)
  useEffect(() => {
    setContentDraft(chunk.content);
    setContextDraft(chunk.context_text ?? "");
    setSavedContent(chunk.content);
    setSavedContext(chunk.context_text ?? "");
    setStatus("idle");
  }, [chunk.id, chunk.content, chunk.context_text]);

  // Autosave — content or context_text 任一改動 debounce 1s 後送 PATCH
  useEffect(() => {
    const contentChanged = contentDraft !== savedContent;
    const contextChanged = contextDraft !== savedContext;
    if (!contentChanged && !contextChanged) return;

    setStatus("saving");
    if (debounceRef.current) window.clearTimeout(debounceRef.current);
    debounceRef.current = window.setTimeout(() => {
      const body: UpdateChunkRequest = {};
      if (contentChanged) body.content = contentDraft;
      if (contextChanged) body.context_text = contextDraft;

      updateMutation.mutate(
        { docId: chunk.document_id, chunkId: chunk.id, body },
        {
          onSuccess: () => {
            setSavedContent(contentDraft);
            setSavedContext(contextDraft);
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
  }, [contentDraft, contextDraft]);

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
      <div className="space-y-3">
        <div>
          <Label className="text-xs text-muted-foreground mb-1 flex items-center gap-1">
            <span>內容（Content）</span>
          </Label>
          <Textarea
            value={contentDraft}
            onChange={(e) => setContentDraft(e.target.value)}
            rows={Math.min(Math.max(contentDraft.split("\n").length, 3), 8)}
            className="text-sm font-mono"
            placeholder="chunk 原始內容"
          />
        </div>
        <div>
          <Label className="text-xs text-muted-foreground mb-1 flex items-center gap-1">
            <Sparkles className="h-3 w-3" />
            <span>AI 上下文摘要（Contextual Retrieval）</span>
            {!chunk.context_text && (
              <span className="italic">· 此 KB 未啟用或尚未生成</span>
            )}
          </Label>
          <Textarea
            value={contextDraft}
            onChange={(e) => setContextDraft(e.target.value)}
            rows={Math.min(
              Math.max(contextDraft.split("\n").length, 2),
              4,
            )}
            className="text-sm"
            placeholder="AI 自動生成的上下文摘要（embedding 會用 context + content 組合文本）"
          />
        </div>
      </div>
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
