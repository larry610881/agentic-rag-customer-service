import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import type { Chunk } from "@/types/chunk";

type Mode = "view" | "edit" | "compact";

interface ChunkCardProps {
  chunk: Chunk;
  mode?: Mode;
  className?: string;
  onClick?: () => void;
  /** edit mode 用：渲染額外操作（傳入 children 可注入按鈕 / textarea）*/
  children?: React.ReactNode;
  /** category 顯示名稱 (optional, 由父元件 lookup) */
  categoryName?: string;
}

const QUALITY_LABEL: Record<string, string> = {
  too_short: "過短",
  incomplete: "斷句不完整",
  duplicate: "重複",
};

export function ChunkCard({
  chunk,
  mode = "view",
  className,
  onClick,
  children,
  categoryName,
}: ChunkCardProps) {
  return (
    <div
      onClick={onClick}
      className={cn(
        "rounded-md border bg-card p-3 text-sm transition-colors",
        onClick && "cursor-pointer hover:bg-muted/50",
        mode === "compact" && "p-2 text-xs",
        className,
      )}
    >
      <div className="flex items-center justify-between gap-2 mb-1">
        <div className="flex items-center gap-2 text-xs text-muted-foreground">
          <span className="font-mono">#{chunk.chunk_index}</span>
          <span className="font-mono truncate max-w-[10ch]" title={chunk.id}>
            {chunk.id.slice(0, 8)}
          </span>
        </div>
        <div className="flex items-center gap-1">
          {chunk.quality_flag && (
            <Badge variant="destructive" className="text-[10px] h-4">
              {QUALITY_LABEL[chunk.quality_flag] ?? chunk.quality_flag}
            </Badge>
          )}
          {categoryName && (
            <Badge variant="secondary" className="text-[10px] h-4">
              {categoryName}
            </Badge>
          )}
          {!categoryName && chunk.category_id && (
            <Badge variant="outline" className="text-[10px] h-4">
              已分類
            </Badge>
          )}
        </div>
      </div>

      {chunk.context_text && mode !== "compact" && (
        <div className="mb-1 text-xs italic text-muted-foreground/80 line-clamp-2">
          {chunk.context_text}
        </div>
      )}

      {mode === "edit" ? (
        children
      ) : (
        <div
          className={cn(
            "whitespace-pre-wrap break-words",
            mode === "compact" ? "line-clamp-2" : "line-clamp-4",
          )}
        >
          {chunk.content}
        </div>
      )}
    </div>
  );
}
