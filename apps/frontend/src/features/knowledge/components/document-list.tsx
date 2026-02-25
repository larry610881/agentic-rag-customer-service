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
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import type { DocumentResponse } from "@/types/knowledge";

interface DocumentListProps {
  documents: DocumentResponse[];
  onDelete?: (docId: string) => void;
  isDeleting?: boolean;
}

function statusVariant(status: DocumentResponse["status"]) {
  switch (status) {
    case "processed":
      return "default" as const;
    case "processing":
      return "secondary" as const;
    case "pending":
      return "outline" as const;
    case "failed":
      return "destructive" as const;
  }
}

export function DocumentList({ documents, onDelete, isDeleting }: DocumentListProps) {
  const [deleteTarget, setDeleteTarget] = useState<DocumentResponse | null>(null);

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
              <th className="px-4 py-2 font-medium">狀態</th>
              <th className="px-4 py-2 font-medium">上傳時間</th>
              {onDelete && <th className="px-4 py-2 font-medium">操作</th>}
            </tr>
          </thead>
          <tbody>
            {documents.map((doc) => (
              <tr key={doc.id} className="border-b">
                <td className="px-4 py-2">{doc.filename}</td>
                <td className="px-4 py-2">{doc.chunk_count}</td>
                <td className="px-4 py-2">
                  <Badge variant={statusVariant(doc.status)}>{doc.status}</Badge>
                </td>
                <td className="px-4 py-2">
                  {new Date(doc.created_at).toLocaleDateString()}
                </td>
                {onDelete && (
                  <td className="px-4 py-2">
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
    </>
  );
}
