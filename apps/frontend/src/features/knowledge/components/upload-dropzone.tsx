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
  const uploadMutation = useUploadDocument();

  const handleFile = useCallback(
    (file: File) => {
      uploadMutation.mutate(
        { knowledgeBaseId, file },
        {
          onSuccess: (data) => {
            onUploadStarted?.(data.task_id);
          },
        },
      );
    },
    [knowledgeBaseId, uploadMutation, onUploadStarted],
  );

  const handleDrop = (e: DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setIsDragOver(false);
    const file = e.dataTransfer.files[0];
    if (file) handleFile(file);
  };

  const handleDragOver = (e: DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setIsDragOver(true);
  };

  const handleDragLeave = () => {
    setIsDragOver(false);
  };

  const handleFileInput = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) handleFile(file);
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
      aria-label="Upload dropzone"
    >
      <p className="text-sm text-muted-foreground">
        Drag and drop a file here, or click to select
      </p>
      <label>
        <Button variant="outline" size="sm" asChild>
          <span>Choose File</span>
        </Button>
        <input
          type="file"
          className="hidden"
          onChange={handleFileInput}
          accept=".pdf,.txt,.md,.docx"
        />
      </label>
      {uploadMutation.isPending && (
        <p className="text-sm text-muted-foreground">Uploading...</p>
      )}
      {uploadMutation.isError && (
        <p className="text-sm text-destructive">Upload failed. Please try again.</p>
      )}
    </div>
  );
}
