import { useMemo, useState } from "react";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { ScrollArea } from "@/components/ui/scroll-area";
import { LoaderCircle, CircleCheck, CircleX, ShieldCheck, ShieldAlert, ShieldX, Eye } from "lucide-react";
import type { DocumentResponse, DocumentQualityStat } from "@/types/knowledge";
import { useReprocessDocument } from "@/hooks/queries/use-documents";
import { ChunkPreviewPanel } from "./chunk-preview-panel";
import { QualityTooltip } from "./quality-tooltip";
import { ReprocessDialog } from "./reprocess-dialog";

interface DocumentListProps {
  kbId: string;
  documents: DocumentResponse[];
  qualityStats?: DocumentQualityStat[];
  onDelete?: (docId: string) => void;
  onBatchDelete?: (docIds: string[]) => void;
  onBatchReprocess?: (docIds: string[]) => void;
  isDeleting?: boolean;
  isBatchDeleting?: boolean;
  isBatchReprocessing?: boolean;
}

function StatusCell({ status }: { status: DocumentResponse["status"] }) {
  switch (status) {
    case "pending":
      return (
        <span className="flex items-center gap-1.5 text-muted-foreground">
          <LoaderCircle className="h-4 w-4 animate-spin" />
          等待中
        </span>
      );
    case "processing":
      return (
        <span className="flex items-center gap-1.5 text-green-600 dark:text-green-400">
          <LoaderCircle className="h-4 w-4 animate-spin" />
          學習中
        </span>
      );
    case "processed":
      return (
        <span className="flex items-center gap-1.5 text-green-600 dark:text-green-400">
          <CircleCheck className="h-4 w-4" />
          完成
        </span>
      );
    case "failed":
      return (
        <span className="flex items-center gap-1.5 text-destructive">
          <CircleX className="h-4 w-4" />
          失敗
        </span>
      );
  }
}

function QualityCell({ score, status }: { score: number; status: DocumentResponse["status"] }) {
  if (status !== "processed") return null;

  if (score >= 0.8) {
    return (
      <span className="flex items-center gap-1.5 text-green-600 dark:text-green-400" data-testid="quality-good">
        <ShieldCheck className="h-4 w-4" />
        {score.toFixed(1)}
      </span>
    );
  }
  if (score >= 0.5) {
    return (
      <span className="flex items-center gap-1.5 text-yellow-600 dark:text-yellow-300" data-testid="quality-warning">
        <ShieldAlert className="h-4 w-4" />
        {score.toFixed(1)}
      </span>
    );
  }
  return (
    <span className="flex items-center gap-1.5 text-red-600 dark:text-red-400" data-testid="quality-poor">
      <ShieldX className="h-4 w-4" />
      {score.toFixed(1)}
    </span>
  );
}

export function DocumentList({
  kbId,
  documents,
  qualityStats,
  onDelete,
  onBatchDelete,
  onBatchReprocess,
  isDeleting,
  isBatchDeleting,
  isBatchReprocessing,
}: DocumentListProps) {
  const [deleteTarget, setDeleteTarget] = useState<DocumentResponse | null>(null);
  const [chunkDoc, setChunkDoc] = useState<DocumentResponse | null>(null);
  const [reprocessTarget, setReprocessTarget] = useState<DocumentResponse | null>(null);
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [showBatchDeleteConfirm, setShowBatchDeleteConfirm] = useState(false);
  const reprocess = useReprocessDocument();

  const statsMap = new Map(
    (qualityStats ?? []).map((s) => [s.document_id, s])
  );

  const selectedFailedCount = useMemo(() => {
    return documents.filter(
      (d) => selectedIds.has(d.id) && d.status === "failed"
    ).length;
  }, [documents, selectedIds]);

  const selectedProcessedCount = useMemo(() => {
    return documents.filter(
      (d) => selectedIds.has(d.id) && d.status === "processed"
    ).length;
  }, [documents, selectedIds]);

  const allSelected = documents.length > 0 && selectedIds.size === documents.length;

  const toggleSelectAll = () => {
    if (allSelected) {
      setSelectedIds(new Set());
    } else {
      setSelectedIds(new Set(documents.map((d) => d.id)));
    }
  };

  const toggleSelect = (id: string) => {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) {
        next.delete(id);
      } else {
        next.add(id);
      }
      return next;
    });
  };

  if (documents.length === 0) {
    return (
      <p className="text-muted-foreground">尚未上傳任何文件。</p>
    );
  }

  return (
    <>
      {selectedIds.size > 0 && (
        <div className="flex items-center gap-3 rounded-md border bg-muted/50 px-4 py-2 text-sm">
          <span className="font-medium">已選 {selectedIds.size} 個文件</span>
          {onBatchReprocess && selectedFailedCount > 0 && (
            <Button
              variant="secondary"
              size="sm"
              disabled={isBatchReprocessing}
              onClick={() => {
                const failedIds = documents
                  .filter((d) => selectedIds.has(d.id) && d.status === "failed")
                  .map((d) => d.id);
                onBatchReprocess(failedIds);
                setSelectedIds(new Set());
              }}
            >
              {isBatchReprocessing ? "重試中..." : `批量重試 (${selectedFailedCount})`}
            </Button>
          )}
          {onBatchReprocess && selectedProcessedCount > 0 && (
            <Button
              variant="outline"
              size="sm"
              disabled={isBatchReprocessing}
              onClick={() => {
                const processedIds = documents
                  .filter((d) => selectedIds.has(d.id) && d.status === "processed")
                  .map((d) => d.id);
                onBatchReprocess(processedIds);
                setSelectedIds(new Set());
              }}
            >
              {isBatchReprocessing ? "處理中..." : `批量重新處理 (${selectedProcessedCount})`}
            </Button>
          )}
          {onBatchDelete && (
            <Button
              variant="destructive"
              size="sm"
              disabled={isBatchDeleting}
              onClick={() => setShowBatchDeleteConfirm(true)}
            >
              {isBatchDeleting ? "刪除中..." : `批量刪除 (${selectedIds.size})`}
            </Button>
          )}
          <Button
            variant="ghost"
            size="sm"
            onClick={() => setSelectedIds(new Set())}
          >
            取消選取
          </Button>
        </div>
      )}

      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b text-left">
              <th className="px-4 py-2 w-10">
                <input
                  type="checkbox"
                  className="h-4 w-4 rounded border-input accent-primary"
                  checked={allSelected}
                  onChange={toggleSelectAll}
                  aria-label="全選"
                />
              </th>
              <th className="px-4 py-2 font-medium">檔案名稱</th>
              <th className="px-4 py-2 font-medium">分塊數</th>
              <th className="px-4 py-2 font-medium">品質</th>
              <th className="px-4 py-2 font-medium">狀態</th>
              <th className="px-4 py-2 font-medium">上傳時間</th>
              {onDelete && <th className="px-4 py-2 font-medium">操作</th>}
            </tr>
          </thead>
          <tbody>
            {documents.map((doc) => (
              <tr key={doc.id} className="group">
                <td className="border-b px-4 py-2">
                  <input
                    type="checkbox"
                    className="h-4 w-4 rounded border-input accent-primary"
                    checked={selectedIds.has(doc.id)}
                    onChange={() => toggleSelect(doc.id)}
                    aria-label={`選取 ${doc.filename}`}
                  />
                </td>
                <td className="border-b px-4 py-2">
                  <div className="flex items-center gap-2">
                    <span>{doc.filename}</span>
                    {(statsMap.get(doc.id)?.negative_feedback_count ?? 0) > 0 && (
                      <span
                        className="inline-flex items-center rounded-full bg-destructive/10 px-2 py-0.5 text-xs font-medium text-destructive"
                        data-testid="negative-feedback-badge"
                      >
                        {statsMap.get(doc.id)!.negative_feedback_count} 差評
                      </span>
                    )}
                  </div>
                </td>
                <td className="border-b px-4 py-2">{doc.chunk_count}</td>
                <td className="border-b px-4 py-2">
                  <QualityTooltip issues={doc.quality_issues}>
                    <span>
                      <QualityCell score={doc.quality_score} status={doc.status} />
                    </span>
                  </QualityTooltip>
                </td>
                <td className="border-b px-4 py-2">
                  <StatusCell status={doc.status} />
                </td>
                <td className="border-b px-4 py-2">
                  {new Date(doc.created_at).toLocaleDateString()}
                </td>
                {onDelete && (
                  <td className="border-b px-4 py-2 space-x-1">
                    {doc.status === "processed" && doc.chunk_count > 0 && (
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => setChunkDoc(doc)}
                      >
                        <Eye className="mr-1 h-4 w-4" />
                        查看分塊
                      </Button>
                    )}
                    {(doc.status === "processed" ||
                      doc.status === "failed") && (
                      <Button
                        variant={
                          doc.status === "failed"
                            ? "secondary"
                            : "outline"
                        }
                        size="sm"
                        onClick={() => setReprocessTarget(doc)}
                      >
                        {doc.status === "failed"
                          ? "重試"
                          : "重新處理"}
                      </Button>
                    )}
                    <Button
                      variant="destructive"
                      size="sm"
                      disabled={isDeleting}
                      onClick={() => setDeleteTarget(doc)}
                    >
                      刪除
                    </Button>
                  </td>
                )}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Single delete confirm */}
      <AlertDialog
        open={!!deleteTarget}
        onOpenChange={(open) => {
          if (!open) setDeleteTarget(null);
        }}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>刪除文件</AlertDialogTitle>
            <AlertDialogDescription>
              確定要刪除「{deleteTarget?.filename}」嗎？
              這將同時移除所有相關的向量資料，且無法復原。
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>取消</AlertDialogCancel>
            <AlertDialogAction
              onClick={() => {
                if (deleteTarget && onDelete) {
                  onDelete(deleteTarget.id);
                  setDeleteTarget(null);
                }
              }}
            >
              刪除
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      {/* Batch delete confirm */}
      <AlertDialog
        open={showBatchDeleteConfirm}
        onOpenChange={(open) => {
          if (!open) setShowBatchDeleteConfirm(false);
        }}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>批量刪除文件</AlertDialogTitle>
            <AlertDialogDescription>
              確定要刪除已選取的 {selectedIds.size} 個文件嗎？
              這將同時移除所有相關的向量資料，且無法復原。
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>取消</AlertDialogCancel>
            <AlertDialogAction
              onClick={() => {
                if (onBatchDelete) {
                  onBatchDelete(Array.from(selectedIds));
                  setSelectedIds(new Set());
                }
                setShowBatchDeleteConfirm(false);
              }}
            >
              刪除
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      <ReprocessDialog
        open={!!reprocessTarget}
        onOpenChange={(open) => {
          if (!open) setReprocessTarget(null);
        }}
        filename={reprocessTarget?.filename ?? ""}
        isPending={reprocess.isPending}
        onConfirm={(params) => {
          if (reprocessTarget) {
            reprocess.mutate({
              knowledgeBaseId: kbId,
              docId: reprocessTarget.id,
              params,
            });
            setReprocessTarget(null);
          }
        }}
      />

      {/* Chunk preview dialog */}
      <Dialog open={!!chunkDoc} onOpenChange={(open) => { if (!open) setChunkDoc(null); }}>
        <DialogContent className="sm:max-w-2xl">
          <DialogHeader>
            <DialogTitle>{chunkDoc?.filename} — 分塊預覽</DialogTitle>
            <DialogDescription>共 {chunkDoc?.chunk_count} 個分塊</DialogDescription>
          </DialogHeader>
          <ScrollArea className="max-h-[60vh] -mx-6 px-6">
            <ChunkPreviewPanel kbId={kbId} docId={chunkDoc?.id ?? ""} open={!!chunkDoc} />
          </ScrollArea>
        </DialogContent>
      </Dialog>
    </>
  );
}
