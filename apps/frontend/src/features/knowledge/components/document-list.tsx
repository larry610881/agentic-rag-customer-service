"use client";

import { useState } from "react";
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
import { LoaderCircle, CircleCheck, CircleX, ShieldCheck, ShieldAlert, ShieldX } from "lucide-react";
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
  isDeleting?: boolean;
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
        <span className="flex items-center gap-1.5 text-green-600">
          <LoaderCircle className="h-4 w-4 animate-spin" />
          學習中
        </span>
      );
    case "processed":
      return (
        <span className="flex items-center gap-1.5 text-green-600">
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
      <span className="flex items-center gap-1.5 text-green-600" data-testid="quality-good">
        <ShieldCheck className="h-4 w-4" />
        {score.toFixed(1)}
      </span>
    );
  }
  if (score >= 0.5) {
    return (
      <span className="flex items-center gap-1.5 text-yellow-600" data-testid="quality-warning">
        <ShieldAlert className="h-4 w-4" />
        {score.toFixed(1)}
      </span>
    );
  }
  return (
    <span className="flex items-center gap-1.5 text-destructive" data-testid="quality-poor">
      <ShieldX className="h-4 w-4" />
      {score.toFixed(1)}
    </span>
  );
}

export function DocumentList({ kbId, documents, qualityStats, onDelete, isDeleting }: DocumentListProps) {
  const [deleteTarget, setDeleteTarget] = useState<DocumentResponse | null>(null);
  const [expandedDocId, setExpandedDocId] = useState<string | null>(null);
  const [reprocessTarget, setReprocessTarget] = useState<DocumentResponse | null>(null);
  const reprocess = useReprocessDocument();

  const statsMap = new Map(
    (qualityStats ?? []).map((s) => [s.document_id, s])
  );

  const colCount = onDelete ? 7 : 6;

  if (documents.length === 0) {
    return (
      <p className="text-muted-foreground">尚未上傳任何文件。</p>
    );
  }

  return (
    <>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b text-left">
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
                  <div className="flex items-center gap-2">
                    <button
                      type="button"
                      className="text-left hover:underline"
                      onClick={() =>
                        setExpandedDocId(expandedDocId === doc.id ? null : doc.id)
                      }
                    >
                      {doc.filename}
                    </button>
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
                    {doc.status === "processed" && (
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => setReprocessTarget(doc)}
                      >
                        重新處理
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
                {expandedDocId === doc.id && (
                  <td colSpan={colCount} className="px-0">
                    <ChunkPreviewPanel
                      kbId={kbId}
                      docId={doc.id}
                      open={true}
                    />
                  </td>
                )}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

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
    </>
  );
}
