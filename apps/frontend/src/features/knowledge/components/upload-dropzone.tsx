import { useCallback, useEffect, useRef, useState, type DragEvent } from "react";
import { Upload } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  useUploadDocument,
  type UploadResumeState,
} from "@/hooks/queries/use-documents";
import { useUploadQueue } from "@/features/knowledge/hooks/use-upload-queue";
import {
  UploadProgressCard,
  type UploadingFileItem,
} from "@/features/knowledge/components/upload-progress-card";
import { cn } from "@/lib/utils";

const MAX_FILE_SIZE = 100 * 1024 * 1024; // 100 MB

const ACCEPTED_TYPES: Record<string, { ext: string; label: string; strategy: string }> = {
  "text/plain":        { ext: ".txt",  label: "純文字",     strategy: "遞迴分塊" },
  "text/markdown":     { ext: ".md",   label: "Markdown",  strategy: "遞迴分塊" },
  "text/csv":          { ext: ".csv",  label: "CSV",       strategy: "逐列分塊" },
  "application/json":  { ext: ".json", label: "JSON",      strategy: "逐筆記錄分塊" },
  "text/xml":          { ext: ".xml",  label: "XML",       strategy: "遞迴分塊" },
  "application/xml":   { ext: ".xml",  label: "XML",       strategy: "遞迴分塊" },
  "text/html":         { ext: ".html", label: "HTML",      strategy: "遞迴分塊" },
  "application/pdf":   { ext: ".pdf",  label: "PDF",       strategy: "依知識庫 OCR 設定" },
  "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
                       { ext: ".docx", label: "Word",      strategy: "遞迴分塊" },
  "application/rtf":   { ext: ".rtf",  label: "RTF",       strategy: "遞迴分塊" },
  "text/rtf":          { ext: ".rtf",  label: "RTF",       strategy: "遞迴分塊" },
  "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet":
                       { ext: ".xlsx", label: "Excel",     strategy: "逐列分塊" },
  "application/vnd.ms-excel":
                       { ext: ".xls",  label: "Excel",     strategy: "逐列分塊" },
};

const ACCEPT_STRING = [...new Set(Object.values(ACCEPTED_TYPES).map((t) => t.ext))].join(",");

function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(0)} MB`;
}

function makeFileId(file: File): string {
  const rand = Math.random().toString(36).slice(2, 8);
  return `${file.name}-${file.size}-${file.lastModified}-${Date.now()}-${rand}`;
}

interface UploadDropzoneProps {
  knowledgeBaseId: string;
}

export function UploadDropzone({ knowledgeBaseId }: UploadDropzoneProps) {
  const [isDragOver, setIsDragOver] = useState(false);
  const [validationErrors, setValidationErrors] = useState<string[]>([]);
  const uploadMutation = useUploadDocument();
  // 批次上傳走佇列：租戶層限流是 100 rpm 且整個租戶共用，一次並發送出 33 個檔
  // 會讓前幾個成功、其餘全部 429（2026-09-08 實測）。
  // resume 由佇列保管、跨重試沿用：429 重試只補做失敗的那一步，
  // 不會重跑 request-upload 而多生一列永遠「等待中」的孤兒文件（Issue #88）。
  const uploadTask = useCallback(
    ({
      file,
      onProgress,
      resume,
    }: {
      file: File;
      onProgress: (pct: number) => void;
      resume: Record<string, unknown>;
    }) =>
      uploadMutation.mutateAsync({
        knowledgeBaseId,
        file,
        onProgress,
        resume: resume as UploadResumeState,
      }),
    [uploadMutation, knowledgeBaseId],
  );
  const {
    items: uploadingFiles,
    stats,
    enqueue,
    retryFailed,
    clearFinished,
  } = useUploadQueue(uploadTask);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const isLocked = stats.uploading > 0 || stats.queued > 0;

  const validateFile = useCallback((file: File): string | null => {
    if (file.size > MAX_FILE_SIZE) {
      return `${file.name}：檔案大小 ${formatSize(file.size)} 超過上限 ${formatSize(MAX_FILE_SIZE)}`;
    }
    const ext = "." + (file.name.split(".").pop()?.toLowerCase() ?? "");
    const validExts = Object.values(ACCEPTED_TYPES).map((t) => t.ext);
    if (!validExts.includes(ext)) {
      return `${file.name}：不支援的檔案格式 (${ext})`;
    }
    return null;
  }, []);

  const handleFiles = useCallback(
    (files: FileList | File[]) => {
      const newErrors: string[] = [];
      const accepted: { id: string; file: File }[] = [];

      for (const file of Array.from(files)) {
        const error = validateFile(file);
        if (error) newErrors.push(error);
        else accepted.push({ id: makeFileId(file), file });
      }

      setValidationErrors(newErrors);
      // 全部丟進佇列，由 useUploadQueue 依伺服器回報的剩餘額度節流送出
      enqueue(accepted);
    },
    [validateFile, enqueue],
  );

  const handleDrop = (e: DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setIsDragOver(false);
    if (isLocked) return;
    if (e.dataTransfer.files.length > 0) {
      handleFiles(e.dataTransfer.files);
    }
  };

  const handleDragOver = (e: DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    if (isLocked) return;
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

  // Deduplicate display entries
  const displayTypes = Object.values(
    Object.values(ACCEPTED_TYPES).reduce<Record<string, { ext: string; label: string; strategy: string }>>(
      (acc, t) => {
        if (!acc[t.ext]) acc[t.ext] = t;
        return acc;
      },
      {},
    ),
  );

  return (
    <div className="space-y-3">
      <div
        onDrop={handleDrop}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        className={cn(
          "flex flex-col items-center justify-center gap-3 rounded-lg border-2 border-dashed p-8 transition-colors",
          isDragOver && !isLocked && "border-primary bg-primary/5",
          !isDragOver && "border-muted",
          isLocked && "opacity-60 cursor-not-allowed",
        )}
        role="region"
        aria-label="上傳區域"
        aria-busy={isLocked}
        aria-disabled={isLocked}
      >
        <Upload className="h-8 w-8 text-muted-foreground" />
        <div className="text-center">
          <p className="text-sm text-muted-foreground">
            拖曳檔案至此處，或點擊選擇檔案
          </p>
          <p className="mt-1 text-xs text-muted-foreground/70">
            單檔上限 {formatSize(MAX_FILE_SIZE)}，支援多檔同時上傳
          </p>
        </div>
        <Button
          type="button"
          variant="outline"
          size="sm"
          disabled={isLocked}
          onClick={() => {
            if (isLocked) return;
            fileInputRef.current?.click();
          }}
        >
          選擇檔案
        </Button>
        <input
          ref={fileInputRef}
          type="file"
          className="hidden"
          onChange={handleFileInput}
          accept={ACCEPT_STRING}
          multiple
          disabled={isLocked}
        />
        {uploadingFiles.length > 0 && (
          <div
            className="mb-2 flex w-full flex-wrap items-center gap-x-3 gap-y-1 text-xs"
            aria-live="polite"
          >
            <span className="font-medium">
              {stats.success} / {stats.total} 完成
            </span>
            {stats.queued > 0 && (
              <span className="text-muted-foreground">
                排隊中 {stats.queued}
              </span>
            )}
            {stats.error > 0 && (
              <span className="text-destructive">失敗 {stats.error}</span>
            )}
            {/* 額度是整個租戶共用的，撞到就整批暫停，這裡把等待秒數說清楚，
                否則使用者會以為卡住了而重新整理、反而讓進度歸零 */}
            {stats.pausedSeconds > 0 && (
              <span className="text-amber-600 dark:text-amber-400">
                已達流量上限，{stats.pausedSeconds} 秒後自動繼續
              </span>
            )}
            {stats.error > 0 && stats.queued === 0 && stats.uploading === 0 && (
              <Button
                type="button"
                size="sm"
                variant="outline"
                className="h-6 px-2 text-xs"
                onClick={retryFailed}
              >
                重試失敗項
              </Button>
            )}
            {stats.success > 0 && (
              <Button
                type="button"
                size="sm"
                variant="ghost"
                className="h-6 px-2 text-xs"
                onClick={clearFinished}
              >
                清除已完成
              </Button>
            )}
          </div>
        )}
        {uploadingFiles.length > 0 && (
          <ul
            aria-label="上傳進度列表"
            className="grid w-full grid-cols-2 gap-3 sm:grid-cols-3 md:grid-cols-4"
          >
            {uploadingFiles.map((f) => (
              <li key={f.id}>
                <UploadProgressCard file={f} />
              </li>
            ))}
          </ul>
        )}
        {validationErrors.length > 0 && (
          <ul className="text-sm text-destructive">
            {validationErrors.map((err, i) => (
              <li key={i}>{err}</li>
            ))}
          </ul>
        )}
      </div>
      <div className="rounded-md border bg-muted/30 px-4 py-3">
        <p className="mb-2 text-xs font-medium text-muted-foreground">支援格式與分割策略</p>
        <div className="flex flex-wrap gap-x-4 gap-y-1">
          {displayTypes.map((t) => (
            <span key={t.ext} className="text-xs text-muted-foreground">
              <span className="font-mono">{t.ext}</span>
              <span className="mx-1 text-muted-foreground/50">·</span>
              {t.strategy}
            </span>
          ))}
        </div>
      </div>
    </div>
  );
}
