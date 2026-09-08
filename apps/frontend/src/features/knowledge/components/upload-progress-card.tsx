import { CircularProgress } from "@/components/ui/circular-progress";
import { cn } from "@/lib/utils";

// queued：已在佇列但尚未送出（批次上傳的節流狀態）
export type UploadFileStatus = "queued" | "uploading" | "success" | "error";

export type UploadingFileItem = {
  id: string;
  name: string;
  progress: number;
  status: UploadFileStatus;
  error?: string;
};

type UploadProgressCardProps = {
  file: UploadingFileItem;
};

export function UploadProgressCard({ file }: UploadProgressCardProps) {
  const ariaLabel =
    file.status === "error"
      ? `上傳失敗：${file.name}`
      : file.status === "success"
        ? `上傳成功：${file.name}`
        : file.status === "queued"
          ? `排隊中：${file.name}`
          : `上傳中：${file.name}`;

  return (
    <div
      className={cn(
        "flex flex-col items-center gap-2 rounded-md border bg-background p-3",
        file.status === "error" && "border-destructive/50",
        file.status === "queued" && "opacity-60",
      )}
    >
      <CircularProgress
        value={file.progress}
        status={file.status}
        size={56}
        strokeWidth={5}
        ariaLabel={ariaLabel}
      />
      <span className="w-full truncate text-center text-xs font-medium" title={file.name}>
        {file.name}
      </span>
      {file.status === "error" && file.error && (
        <span className="w-full truncate text-center text-xs text-destructive" title={file.error}>
          {file.error}
        </span>
      )}
    </div>
  );
}
