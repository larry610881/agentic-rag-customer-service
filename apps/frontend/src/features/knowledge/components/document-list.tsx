import { useMemo, useState } from "react";
import { formatDate } from "@/lib/format-date";
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
import { LoaderCircle, CircleCheck, CircleX, ShieldCheck, ShieldAlert, ShieldX, Eye, FileText, FileSpreadsheet, FileJson, FileType } from "lucide-react";
import { API_ENDPOINTS } from "@/lib/api-endpoints";
import { API_BASE } from "@/lib/api-config";
import { useAuthStore } from "@/stores/use-auth-store";
import type { DocumentResponse, DocumentQualityStat } from "@/types/knowledge";
import { useReprocessDocument } from "@/hooks/queries/use-documents";
import { ChunkPreviewPanel } from "./chunk-preview-panel";
import { QualityTooltip } from "./quality-tooltip";
import { ReprocessDialog } from "./reprocess-dialog";

// Browser-viewable content types (can open in new tab)
const BROWSER_VIEWABLE = new Set([
  "text/plain",
  "text/markdown",
  "text/csv",
  "text/html",
  "text/xml",
  "application/json",
  "application/xml",
  "application/pdf",
]);

const CONTENT_TYPE_MAP: Record<string, { label: string; icon: typeof FileText; color: string }> = {
  "application/pdf": { label: "PDF", icon: FileText, color: "text-red-600 bg-red-50 dark:bg-red-950 dark:text-red-400" },
  "text/csv": { label: "CSV", icon: FileSpreadsheet, color: "text-green-600 bg-green-50 dark:bg-green-950 dark:text-green-400" },
  "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": { label: "XLSX", icon: FileSpreadsheet, color: "text-green-600 bg-green-50 dark:bg-green-950 dark:text-green-400" },
  "application/json": { label: "JSON", icon: FileJson, color: "text-amber-600 bg-amber-50 dark:bg-amber-950 dark:text-amber-400" },
  "text/plain": { label: "TXT", icon: FileType, color: "text-slate-600 bg-slate-50 dark:bg-slate-950 dark:text-slate-400" },
  "text/markdown": { label: "MD", icon: FileType, color: "text-purple-600 bg-purple-50 dark:bg-purple-950 dark:text-purple-400" },
};

function ContentTypeBadge({ contentType, onClick }: { contentType: string; onClick?: () => void }) {
  const info = CONTENT_TYPE_MAP[contentType];
  const label = info?.label ?? contentType.split("/").pop()?.toUpperCase() ?? "?";
  const Icon = info?.icon ?? FileType;
  const color = info?.color ?? "text-muted-foreground bg-muted";
  return (
    <button
      type="button"
      onClick={onClick}
      title="查看原始檔"
      className={`inline-flex items-center gap-1 rounded px-1.5 py-0.5 text-xs font-medium cursor-pointer hover:opacity-70 transition-opacity ${color}`}
    >
      <Icon className="h-3 w-3" />
      {label}
    </button>
  );
}

async function openDocumentPreview(
  kbId: string,
  doc: DocumentResponse,
  setTextPreviewDoc: (d: DocumentResponse) => void,
  setTextPreviewContent: (t: string) => void,
) {
  const token = useAuthStore.getState().token;
  const headers: Record<string, string> = token
    ? { Authorization: `Bearer ${token}` }
    : {};
  const canPreview = BROWSER_VIEWABLE.has(doc.content_type);

  // 1. Try preview-url API (GCS → signed URL)
  try {
    const puRes = await fetch(
      `${API_BASE}${API_ENDPOINTS.documents.previewUrl(kbId, doc.id)}`,
      { headers },
    );
    if (puRes.ok) {
      const pu = await puRes.json();
      if (pu.preview_url) {
        window.open(pu.preview_url, '_blank');
        return;
      }
    }
  } catch { /* fallback below */ }

  // 2. Local: browser-viewable → fetch blob
  if (canPreview) {
    const url = `${API_BASE}${API_ENDPOINTS.documents.view(kbId, doc.id)}`;
    const w = window.open('', '_blank');
    try {
      const res = await fetch(url, { headers });
      if (!res.ok) throw new Error(`${res.status}`);
      const blob = await res.blob();
      const blobUrl = URL.createObjectURL(blob);
      if (w) w.location.href = blobUrl;
      else window.open(blobUrl, '_blank');
    } catch {
      if (w) w.close();
    }
  } else {
    // 3. Binary → show parsed text dialog
    const url = `${API_BASE}${API_ENDPOINTS.documents.chunks(kbId, doc.id)}`;
    try {
      const res = await fetch(url, { headers });
      if (!res.ok) throw new Error(`${res.status}`);
      const data = await res.json();
      const chunks = data.items ?? data ?? [];
      const text = chunks
        .map((c: { content: string }) => c.content)
        .join('\n\n---\n\n');
      setTextPreviewContent(text || '（無內容）');
      setTextPreviewDoc(doc);
    } catch {
      setTextPreviewContent('無法載入文件內容');
      setTextPreviewDoc(doc);
    }
  }
}

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

function StatusCell({ status, taskProgress }: { status: DocumentResponse["status"]; taskProgress?: number | null }) {
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
        <div className="flex flex-col gap-1">
          <span className="flex items-center gap-1.5 text-green-600 dark:text-green-400">
            <LoaderCircle className="h-4 w-4 animate-spin" />
            學習中{taskProgress != null ? ` ${taskProgress}%` : ""}
          </span>
          {taskProgress != null && (
            <div className="h-1.5 w-24 rounded-full bg-muted overflow-hidden">
              <div
                className="h-full rounded-full bg-green-500 transition-all duration-500"
                style={{ width: `${taskProgress}%` }}
              />
            </div>
          )}
        </div>
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
  const [textPreviewDoc, setTextPreviewDoc] = useState<DocumentResponse | null>(null);
  const [textPreviewContent, setTextPreviewContent] = useState<string>("");
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
                    <ContentTypeBadge
                      contentType={doc.content_type}
                      onClick={() => openDocumentPreview(kbId, doc, setTextPreviewDoc, setTextPreviewContent)}
                    />
                    <span>{doc.filename.replace(/\.[^.]+$/, '')}</span>
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
                  <StatusCell status={doc.status} taskProgress={doc.task_progress} />
                </td>
                <td className="border-b px-4 py-2">
                  {formatDate(doc.created_at)}
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

      {/* Text preview dialog (for binary formats: docx, xlsx, rtf, xls) */}
      <Dialog open={!!textPreviewDoc} onOpenChange={(open) => { if (!open) { setTextPreviewDoc(null); setTextPreviewContent(""); } }}>
        <DialogContent className="sm:max-w-3xl">
          <DialogHeader>
            <DialogTitle>{textPreviewDoc?.filename} — 文件內容</DialogTitle>
            <DialogDescription>
              此格式無法在瀏覽器直接預覽，以下為解析後的文字內容
            </DialogDescription>
          </DialogHeader>
          <ScrollArea className="max-h-[70vh] -mx-6 px-6">
            <pre className="whitespace-pre-wrap text-sm leading-relaxed">
              {textPreviewContent}
            </pre>
          </ScrollArea>
        </DialogContent>
      </Dialog>
    </>
  );
}
