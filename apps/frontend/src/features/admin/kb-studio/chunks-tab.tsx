import { useEffect, useMemo, useRef, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { useVirtualizer } from "@tanstack/react-virtual";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { ChevronLeft, ChevronRight, AlertTriangle } from "lucide-react";
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
  const [searchParams, setSearchParams] = useSearchParams();
  const highlightChunkId = searchParams.get("highlight");

  const [page, setPage] = useState(1);
  const [categoryId, setCategoryId] = useState<string | "all">("all");
  // QualityEdit.1 P2: 低品質 filter（quality_flag != null 的 chunk，通常是 "low_quality" / "duplicate"）
  const [lowQualityOnly, setLowQualityOnly] = useState(false);

  const { data: categories } = useCategoriesQuery(kbId);
  const { data, isLoading, error } = useKbChunks({
    kbId,
    page,
    pageSize: PAGE_SIZE,
    categoryId: categoryId === "all" ? undefined : categoryId,
  });

  const allItems = data?.items ?? [];
  // Frontend filter（backend API 暫無 quality_flag filter，避免動 API）
  const items = useMemo(
    () => (lowQualityOnly ? allItems.filter((c) => c.quality_flag) : allItems),
    [allItems, lowQualityOnly],
  );
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

  // QualityEdit.1 P0: ?highlight=<chunkId> 自動 scroll 到該 chunk
  useEffect(() => {
    if (!highlightChunkId || items.length === 0) return;
    const idx = items.findIndex((c) => c.id === highlightChunkId);
    if (idx >= 0) {
      virtualizer.scrollToIndex(idx, { align: "center", behavior: "smooth" });
    }
    // 標亮之後不清 query param，讓使用者 refresh 也能維持（刻意不清）
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [highlightChunkId, items.length]);

  return (
    <div className="flex flex-col h-full gap-3">
      <div className="flex items-center justify-between gap-2 flex-wrap">
        <div className="flex items-center gap-3 flex-wrap">
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
          {/* QualityEdit.1 P2: 低品質 filter */}
          <div className="flex items-center gap-2">
            <Switch
              id="lowq-filter"
              checked={lowQualityOnly}
              onCheckedChange={setLowQualityOnly}
            />
            <Label
              htmlFor="lowq-filter"
              className="text-sm flex items-center gap-1 cursor-pointer"
            >
              <AlertTriangle className="h-3.5 w-3.5 text-amber-500" />
              只看低品質
            </Label>
          </div>
          <span className="text-sm text-muted-foreground">
            共 {total} chunks · 本頁顯示 {items.length} · 第 {page} / {totalPages} 頁
          </span>
          {highlightChunkId && (
            <span className="text-xs bg-primary/10 text-primary px-2 py-1 rounded border border-primary/20">
              已跳轉至 chunk {highlightChunkId.slice(0, 8)}...
              <button
                className="ml-2 hover:underline"
                onClick={() => {
                  const next = new URLSearchParams(searchParams);
                  next.delete("highlight");
                  setSearchParams(next, { replace: true });
                }}
              >
                清除
              </button>
            </span>
          )}
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
            const isHighlighted = chunk.id === highlightChunkId;
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
                className={
                  isHighlighted
                    ? "ring-2 ring-primary ring-offset-2 rounded-md"
                    : undefined
                }
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
