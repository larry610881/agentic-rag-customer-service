import { useCallback, useState, type DragEvent } from "react";
import { Upload } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useUploadDocument } from "@/hooks/queries/use-documents";

const MAX_FILE_SIZE = 32 * 1024 * 1024; // 32 MB

const ACCEPTED_TYPES: Record<string, { ext: string; label: string; strategy: string }> = {
  "text/plain":        { ext: ".txt",  label: "純文字",     strategy: "遞迴分塊" },
  "text/markdown":     { ext: ".md",   label: "Markdown",  strategy: "遞迴分塊" },
  "text/csv":          { ext: ".csv",  label: "CSV",       strategy: "逐列分塊" },
  "application/json":  { ext: ".json", label: "JSON",      strategy: "遞迴分塊" },
  "text/xml":          { ext: ".xml",  label: "XML",       strategy: "遞迴分塊" },
  "application/xml":   { ext: ".xml",  label: "XML",       strategy: "遞迴分塊" },
  "text/html":         { ext: ".html", label: "HTML",      strategy: "遞迴分塊" },
  "application/pdf":   { ext: ".pdf",  label: "PDF",       strategy: "遞迴分塊" },
  "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
                       { ext: ".docx", label: "Word",      strategy: "遞迴分塊" },
  "application/rtf":   { ext: ".rtf",  label: "RTF",       strategy: "遞迴分塊" },
  "text/rtf":          { ext: ".rtf",  label: "RTF",       strategy: "遞迴分塊" },
  "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet":
                       { ext: ".xlsx", label: "Excel",     strategy: "逐列分塊" },
  "application/vnd.ms-excel":
                       { ext: ".xls",  label: "Excel",     strategy: "逐列分塊" },
  "application/sql":   { ext: ".sql",  label: "SQL",       strategy: "SQL 語句分塊" },
};

const ACCEPT_STRING = [...new Set(Object.values(ACCEPTED_TYPES).map((t) => t.ext))].join(",");

function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(0)} MB`;
}

interface UploadDropzoneProps {
  knowledgeBaseId: string;
}

export function UploadDropzone({ knowledgeBaseId }: UploadDropzoneProps) {
  const [isDragOver, setIsDragOver] = useState(false);
  const [pendingCount, setPendingCount] = useState(0);
  const [errors, setErrors] = useState<string[]>([]);
  const uploadMutation = useUploadDocument();

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
      const fileArray = Array.from(files);
      const newErrors: string[] = [];
      const validFiles: File[] = [];

      for (const file of fileArray) {
        const error = validateFile(file);
        if (error) {
          newErrors.push(error);
        } else {
          validFiles.push(file);
        }
      }

      setErrors(newErrors);
      if (validFiles.length === 0) return;

      setPendingCount((c) => c + validFiles.length);
      for (const file of validFiles) {
        uploadMutation
          .mutateAsync({ knowledgeBaseId, file })
          .catch(() => {
            setErrors((prev) => [...prev, `${file.name}：上傳失敗`]);
          })
          .finally(() => {
            setPendingCount((c) => c - 1);
          });
      }
    },
    [knowledgeBaseId, uploadMutation, validateFile],
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
        className={`flex flex-col items-center justify-center gap-3 rounded-lg border-2 border-dashed p-8 transition-colors ${
          isDragOver ? "border-primary bg-primary/5" : "border-muted"
        }`}
        role="region"
        aria-label="上傳區域"
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
        <label>
          <Button variant="outline" size="sm" asChild>
            <span>選擇檔案</span>
          </Button>
          <input
            type="file"
            className="hidden"
            onChange={handleFileInput}
            accept={ACCEPT_STRING}
            multiple
          />
        </label>
        {pendingCount > 0 && (
          <p className="text-sm text-muted-foreground">
            正在上傳 {pendingCount} 個檔案...
          </p>
        )}
        {errors.length > 0 && (
          <ul className="text-sm text-destructive">
            {errors.map((err, i) => (
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
