import { useMemo } from "react";
import { cn } from "@/lib/utils";
import type { Source } from "@/types/chat";

export interface SourceImageGalleryProps {
  sources: Source[];
  /**
   * full: 多欄 grid，適合 Web Bot 寬畫面
   * compact: 單欄或窄 grid，適合 Widget 嵌入窗
   */
  variant?: "full" | "compact";
  className?: string;
}

interface ImageItem {
  src: string;
  documentId: string;
  documentName: string;
  pageNumber?: number;
  score: number;
}

/**
 * 從 sources 過濾出有 image_url 的項目，並以 (document_id, page_number)
 * 去重保留分數最高者。
 */
function extractImages(sources: Source[]): ImageItem[] {
  const best = new Map<string, ImageItem>();
  for (const s of sources) {
    if (!s.image_url) continue;
    const key = `${s.document_id ?? ""}#${s.page_number ?? ""}`;
    const existing = best.get(key);
    if (!existing || s.score > existing.score) {
      best.set(key, {
        src: s.image_url,
        documentId: s.document_id ?? "",
        documentName: s.document_name,
        pageNumber: s.page_number,
        score: s.score,
      });
    }
  }
  return [...best.values()];
}

export function SourceImageGallery({
  sources,
  variant = "full",
  className,
}: SourceImageGalleryProps) {
  const images = useMemo(() => extractImages(sources), [sources]);

  if (images.length === 0) return null;

  return (
    <div
      className={cn("flex flex-col gap-2", className)}
      data-variant={variant}
    >
      <p className="text-xs font-medium text-muted-foreground">
        參考圖片（{images.length}）
      </p>
      <div
        className={cn(
          "grid gap-2",
          variant === "full"
            ? "grid-cols-2 sm:grid-cols-3"
            : "grid-cols-2",
        )}
      >
        {images.map((img) => (
          <a
            key={`${img.documentId}#${img.pageNumber ?? ""}#${img.src}`}
            href={img.src}
            target="_blank"
            rel="noopener noreferrer"
            className={cn(
              "group relative block overflow-hidden rounded-md border bg-muted/30",
              "transition-shadow duration-200 hover:shadow-md",
              "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/50",
            )}
            title={`${img.documentName}${
              img.pageNumber != null ? ` · 第 ${img.pageNumber} 頁` : ""
            }`}
          >
            <img
              src={img.src}
              alt={`${img.documentName}${
                img.pageNumber != null ? ` 第 ${img.pageNumber} 頁` : ""
              }`}
              loading="lazy"
              className={cn(
                "w-full object-cover transition-transform duration-200",
                "group-hover:scale-[1.02]",
                variant === "full" ? "aspect-[3/4]" : "aspect-square",
              )}
            />
            <div
              className={cn(
                "absolute bottom-0 left-0 right-0",
                "bg-gradient-to-t from-black/60 to-transparent",
                "px-2 py-1 text-[10px] text-white truncate",
              )}
            >
              {img.documentName}
              {img.pageNumber != null && ` · p.${img.pageNumber}`}
            </div>
          </a>
        ))}
      </div>
    </div>
  );
}
