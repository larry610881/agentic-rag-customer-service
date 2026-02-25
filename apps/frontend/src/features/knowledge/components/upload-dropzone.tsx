"use client";

import { useCallback, useState, type DragEvent } from "react";
import { Button } from "@/components/ui/button";
import { useUploadDocument } from "@/hooks/queries/use-documents";

interface UploadDropzoneProps {
  knowledgeBaseId: string;
  onUploadStarted?: (taskId: string) => void;
}

export function UploadDropzone({ knowledgeBaseId, onUploadStarted }: UploadDropzoneProps) {
  const [isDragOver, setIsDragOver] = useState(false);
  const [pendingCount, setPendingCount] = useState(0);
  const uploadMutation = useUploadDocument();

  const handleFiles = useCallback(
    (files: FileList | File[]) => {
      const fileArray = Array.from(files);
      setPendingCount((c) => c + fileArray.length);
      for (const file of fileArray) {
        uploadMutation
          .mutateAsync({ knowledgeBaseId, file })
          .then((data) => {
            onUploadStarted?.(data.task_id);
          })
          .finally(() => {
            setPendingCount((c) => c - 1);
          });
      }
    },
    [knowledgeBaseId, uploadMutation, onUploadStarted],
  );

  const handleDrop = (e: DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setIsDragOver(false);
    if (e.dataTransfer.files.length > 0) {
      handleFiles(e.dataTransfer.files);
    }
  };

  const handleDragOver = (e: DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setIsDragOver(true);
  };

  const handleDragLeave = () => {
    setIsDragOver(false);
  };

  const handleFileInput = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (files && files.length > 0) {
      handleFiles(files);
    }
    e.target.value = "";
  };

  return (
    <div
      onDrop={handleDrop}
      onDragOver={handleDragOver}
      onDragLeave={handleDragLeave}
      className={`flex flex-col items-center justify-center gap-2 rounded-lg border-2 border-dashed p-8 transition-colors ${
        isDragOver ? "border-primary bg-primary/5" : "border-muted"
      }`}
      role="region"
      aria-label="上傳區域"
    >
      <p className="text-sm text-muted-foreground">
        拖曳檔案至此處，或點擊選擇檔案
      </p>
      <label>
        <Button variant="outline" size="sm" asChild>
          <span>選擇檔案</span>
        </Button>
        <input
          type="file"
          className="hidden"
          onChange={handleFileInput}
          accept=".pdf,.txt,.md,.docx"
          multiple
        />
      </label>
      {pendingCount > 0 && (
        <p className="text-sm text-muted-foreground">
          正在上傳 {pendingCount} 個檔案...
        </p>
      )}
      {uploadMutation.isError && (
        <p className="text-sm text-destructive">上傳失敗，請重試。</p>
      )}
    </div>
  );
}
