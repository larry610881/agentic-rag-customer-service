import { useRef, useState } from "react";
import { useVirtualizer } from "@tanstack/react-virtual";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ChevronLeft, ChevronRight } from "lucide-react";
import { useKbChunks } from "@/hooks/queries/use-kb-chunks";
import { useCategoriesQuery } from "@/hooks/queries/use-categories";
import { ChunkEditor } from "@/features/admin/kb-studio/chunk-editor";

interface ChunksTabProps {
  kbId: string;
}

const PAGE_SIZE = 50;
const ESTIMATE_ITEM_HEIGHT = 220;

export function ChunksTab({ kbId }: ChunksTabProps) {
  const parentRef = useRef<HTMLDivElement>(null);
  const [page, setPage] = useState(1);
  const [categoryId, setCategoryId] = useState<string | "all">("all");

  const { data: categories } = useCategoriesQuery(kbId);
  const { data, isLoading, error } = useKbChunks({
    kbId,
    page,
    pageSize: PAGE_SIZE,
    categoryId: categoryId === "all" ? undefined : categoryId,
  });

  const items = data?.items ?? [];
  const total = data?.total ?? 0;
  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));

  const virtualizer = useVirtualizer({
    count: items.length,
    getScrollElement: () => parentRef.current,
    estimateSize: () => ESTIMATE_ITEM_HEIGHT,
    overscan: 5,
  });

  const categoryNameMap = new Map(
    (categories ?? []).map((c) => [c.id, c.name]),
  );

  return (
    <div className="flex flex-col h-full gap-3">
      <div className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <select
            className="flex h-9 rounded-md border border-input bg-transparent px-3 py-1 text-sm shadow-sm"
            value={categoryId}
            onChange={(e) => {
              setCategoryId(e.target.value);
              setPage(1);
            }}
          >
            <option value="all">全部分類</option>
            {(categories ?? []).map((c) => (
              <option key={c.id} value={c.id}>
                {c.name} ({c.chunk_count})
              </option>
            ))}
          </select>
          <span className="text-sm text-muted-foreground">
            共 {total} chunks · 第 {page} / {totalPages} 頁
          </span>
        </div>
        <div className="flex items-center gap-1">
          <Button
            variant="outline"
            size="icon"
            disabled={page <= 1}
            onClick={() => setPage((p) => Math.max(1, p - 1))}
          >
            <ChevronLeft className="h-4 w-4" />
          </Button>
          <Input
            className="w-16 text-center"
            type="number"
            value={page}
            onChange={(e) =>
              setPage(Math.max(1, Math.min(totalPages, Number(e.target.value) || 1)))
            }
          />
          <Button
            variant="outline"
            size="icon"
            disabled={page >= totalPages}
            onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
          >
            <ChevronRight className="h-4 w-4" />
          </Button>
        </div>
      </div>

      {isLoading && <div className="text-muted-foreground">載入中...</div>}
      {error && (
        <div className="text-destructive">
          載入失敗：{(error as Error).message}
        </div>
      )}
      {!isLoading && items.length === 0 && (
        <div className="text-muted-foreground py-8 text-center">
          {categoryId === "all" ? "此 KB 尚無 chunks" : "此分類無 chunks"}
        </div>
      )}

      <div
        ref={parentRef}
        className="flex-1 overflow-auto rounded-md border"
        style={{ contain: "strict" }}
      >
        <div
          style={{
            height: `${virtualizer.getTotalSize()}px`,
            width: "100%",
            position: "relative",
          }}
        >
          {virtualizer.getVirtualItems().map((virtualRow) => {
            const chunk = items[virtualRow.index];
            return (
              <div
                key={chunk.id}
                data-index={virtualRow.index}
                ref={virtualizer.measureElement}
                style={{
                  position: "absolute",
                  top: 0,
                  left: 0,
                  width: "100%",
                  transform: `translateY(${virtualRow.start}px)`,
                  padding: "4px 8px",
                }}
              >
                <ChunkEditor
                  chunk={chunk}
                  kbId={kbId}
                  categoryName={
                    chunk.category_id
                      ? categoryNameMap.get(chunk.category_id)
                      : undefined
                  }
                />
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
