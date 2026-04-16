import { useState } from "react";
import { AlertTriangle, ChevronDown, ChevronRight, Loader2, Tag } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import {
  useCategories,
} from "@/features/knowledge/hooks/use-categories";
import { useCategoryChunks } from "@/features/knowledge/hooks/use-category-chunks";
import type { DocumentResponse } from "@/types/knowledge";

type CategoryListProps = {
  kbId: string;
  documents?: DocumentResponse[];
};

export function CategoryList({ kbId, documents }: CategoryListProps) {
  const hasProcessing = documents?.some(
    (d) => d.status === "pending" || d.status === "processing"
  );

  const { data: categories, isLoading } = useCategories(kbId, !!hasProcessing);
  const [expandedId, setExpandedId] = useState<string | null>(null);

  const toggleExpand = (catId: string) => {
    setExpandedId(expandedId === catId ? null : catId);
  };

  return (
    <div className="flex flex-col gap-3">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-medium flex items-center gap-1.5">
          <Tag className="h-4 w-4" />
          自動分類
          {hasProcessing && (
            <span className="inline-flex items-center gap-1 text-xs text-muted-foreground font-normal">
              <Loader2 className="h-3 w-3 animate-spin" />
              文件處理完成後自動分類
            </span>
          )}
        </h3>
      </div>

      {isLoading && (
        <div className="text-sm text-muted-foreground">載入中...</div>
      )}

      {!isLoading && (!categories || categories.length === 0) && (
        <div className="text-sm text-muted-foreground rounded-md border border-dashed p-4 text-center">
          {hasProcessing
            ? "文件處理中，完成後將自動產生分類..."
            : "尚無分類。上傳文件處理完成後自動產生。"}
        </div>
      )}

      {categories && categories.length > 0 && (
        <div className="flex flex-col gap-1.5">
          {categories.map((cat) => (
            <div key={cat.id} className="flex flex-col">
              <button
                className="flex items-center justify-between rounded-md border px-3 py-2 hover:bg-muted/50 transition-colors duration-150 w-full text-left"
                onClick={() => toggleExpand(cat.id)}
              >
                <div className="flex items-center gap-1.5">
                  {expandedId === cat.id ? (
                    <ChevronDown className="h-3.5 w-3.5" />
                  ) : (
                    <ChevronRight className="h-3.5 w-3.5" />
                  )}
                  <span className="text-sm">{cat.name}</span>
                </div>
                <Badge variant="secondary" className="text-xs">
                  {cat.chunk_count} chunks
                </Badge>
              </button>

              {expandedId === cat.id && (
                <CategoryChunksPanel kbId={kbId} categoryId={cat.id} />
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function CategoryChunksPanel({
  kbId,
  categoryId,
}: {
  kbId: string;
  categoryId: string;
}) {
  const { data, isLoading } = useCategoryChunks(kbId, categoryId);

  if (isLoading) {
    return (
      <div className="ml-6 mt-1 text-xs text-muted-foreground">
        <Loader2 className="h-3 w-3 animate-spin inline mr-1" />
        載入 chunks...
      </div>
    );
  }

  if (!data || data.chunks.length === 0) {
    return (
      <div className="ml-6 mt-1 text-xs text-muted-foreground">
        此分類沒有 chunks。
      </div>
    );
  }

  return (
    <div className="ml-6 mt-1 flex flex-col gap-2">
      {data.chunks.map((chunk) => (
        <div
          key={chunk.id}
          className="rounded border px-3 py-3 text-xs bg-muted/30"
        >
          <div className="flex items-center justify-between mb-2">
            <span className="text-muted-foreground font-medium">
              #{chunk.chunk_index}
            </span>
            <span
              className={`font-mono ${
                chunk.cohesion_score < 0.5
                  ? "text-destructive"
                  : chunk.cohesion_score < 0.7
                    ? "text-yellow-600"
                    : "text-green-600"
              }`}
            >
              {chunk.cohesion_score < 0.5 && (
                <AlertTriangle className="h-3 w-3 inline mr-0.5" />
              )}
              聚合度: {chunk.cohesion_score.toFixed(2)}
            </span>
          </div>
          <p className="text-foreground whitespace-pre-wrap">{chunk.content}</p>
          {chunk.context_text && (
            <p className="mt-2 text-muted-foreground italic border-t pt-2">
              AI: {chunk.context_text}
            </p>
          )}
        </div>
      ))}
    </div>
  );
}
