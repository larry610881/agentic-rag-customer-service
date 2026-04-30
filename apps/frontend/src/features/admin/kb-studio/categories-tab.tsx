import { useState } from "react";
import { GripVertical, Plus, Trash2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  useAssignChunks,
  useCategoriesQuery,
  useCreateCategory,
  useDeleteCategory,
} from "@/hooks/queries/use-categories";
import { useKbChunks } from "@/hooks/queries/use-kb-chunks";
import { ChunkCard } from "@/features/knowledge/components/chunk-card";
import { ConfirmDangerDialog } from "@/components/ui/confirm-danger-dialog";
import type { ChunkCategory } from "@/types/chunk";
import { cn } from "@/lib/utils";

interface CategoriesTabProps {
  kbId: string;
}

export function CategoriesTab({ kbId }: CategoriesTabProps) {
  const { data: categories } = useCategoriesQuery(kbId);
  const create = useCreateCategory(kbId);
  const del = useDeleteCategory(kbId);
  const assign = useAssignChunks(kbId);

  const [newName, setNewName] = useState("");
  const [pendingDelete, setPendingDelete] = useState<ChunkCategory | null>(null);
  const [activeCategoryId, setActiveCategoryId] = useState<string | "uncat">(
    "uncat",
  );
  // 拖曳狀態：哪個 chunk 在拖、哪個 category row 是 hover target
  const [draggingChunkId, setDraggingChunkId] = useState<string | null>(null);
  const [hoverCatId, setHoverCatId] = useState<string | null>(null);
  const [recentAssign, setRecentAssign] = useState<{
    catId: string;
    chunkId: string;
  } | null>(null);

  // 取目前 active filter 的 chunks（前 100，足夠拖拉用）
  const { data: chunkPage } = useKbChunks({
    kbId,
    page: 1,
    pageSize: 100,
    categoryId: activeCategoryId === "uncat" ? undefined : activeCategoryId,
  });

  const handleCreate = () => {
    if (!newName.trim()) return;
    create.mutate(
      { name: newName.trim() },
      { onSuccess: () => setNewName("") },
    );
  };

  // HTML5 native drag — chunk → category
  const handleDragStart = (e: React.DragEvent, chunkId: string) => {
    e.dataTransfer.effectAllowed = "move";
    e.dataTransfer.setData("text/chunk-id", chunkId);
    setDraggingChunkId(chunkId);
  };

  const handleDragEnd = () => {
    setDraggingChunkId(null);
    setHoverCatId(null);
  };

  const handleDropToCategory = (e: React.DragEvent, catId: string) => {
    e.preventDefault();
    const chunkId = e.dataTransfer.getData("text/chunk-id");
    setDraggingChunkId(null);
    setHoverCatId(null);
    if (!chunkId) return;
    assign.mutate(
      { catId, chunkIds: [chunkId] },
      {
        onSuccess: () => {
          setRecentAssign({ catId, chunkId });
          window.setTimeout(() => setRecentAssign(null), 2500);
        },
      },
    );
  };

  const allowDrop = (e: React.DragEvent, catId: string) => {
    e.preventDefault();
    e.dataTransfer.dropEffect = "move";
    if (hoverCatId !== catId) setHoverCatId(catId);
  };

  const handleDragLeaveCat = (catId: string) => {
    if (hoverCatId === catId) setHoverCatId(null);
  };

  // 鍵盤 a11y：點 chunk 把它「選起來」，再點分類列即可指派（pseudo drag）
  const [keyboardSelected, setKeyboardSelected] = useState<string | null>(null);
  const assignByClick = (catId: string) => {
    if (!keyboardSelected) {
      setActiveCategoryId(catId);
      return;
    }
    assign.mutate(
      { catId, chunkIds: [keyboardSelected] },
      {
        onSuccess: () => {
          setRecentAssign({ catId, chunkId: keyboardSelected });
          window.setTimeout(() => setRecentAssign(null), 2500);
          setKeyboardSelected(null);
        },
      },
    );
  };

  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 h-full">
      {/* 左：分類列表 + CRUD */}
      <div className="space-y-3 overflow-y-auto">
        <div className="flex items-center gap-2">
          <Input
            placeholder="新分類名稱"
            value={newName}
            onChange={(e) => setNewName(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleCreate()}
          />
          <Button
            onClick={handleCreate}
            disabled={create.isPending || !newName.trim()}
          >
            <Plus className="h-4 w-4 mr-1" />
            新增
          </Button>
        </div>
        <div className="rounded-md border">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>分類</TableHead>
                <TableHead className="text-right">chunks</TableHead>
                <TableHead className="w-[50px]">操作</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {/* 「未分類」也要可拖回 — 之前漏接：分類過後想撤回沒辦法 */}
              <TableRow
                onDragOver={(e) => allowDrop(e, "__uncat__")}
                onDragLeave={() => handleDragLeaveCat("__uncat__")}
                onDrop={(e) => handleDropToCategory(e, "")}
                className={cn(
                  "cursor-pointer transition-colors",
                  activeCategoryId === "uncat" && "bg-muted/50",
                  draggingChunkId &&
                    hoverCatId === "__uncat__" &&
                    "ring-2 ring-amber-400 bg-amber-50 dark:bg-amber-900/20",
                  draggingChunkId &&
                    hoverCatId !== "__uncat__" &&
                    "border-dashed",
                )}
                onClick={() => assignByClick("__uncat__")}
              >
                <TableCell className="text-muted-foreground italic">
                  {keyboardSelected
                    ? "👆 點此撤銷分類（移為未分類）"
                    : draggingChunkId
                      ? "👈 拖到這裡 = 移為未分類"
                      : "(未分類)"}
                </TableCell>
                <TableCell className="text-right">—</TableCell>
                <TableCell />
              </TableRow>
              {(categories ?? []).map((c) => {
                const isHover =
                  draggingChunkId != null && hoverCatId === c.id;
                const isRecent =
                  recentAssign?.catId === c.id &&
                  recentAssign?.chunkId != null;
                return (
                  <TableRow
                    key={c.id}
                    onDragOver={(e) => allowDrop(e, c.id)}
                    onDragLeave={() => handleDragLeaveCat(c.id)}
                    onDrop={(e) => handleDropToCategory(e, c.id)}
                    className={cn(
                      "cursor-pointer transition-colors",
                      activeCategoryId === c.id && "bg-muted/50",
                      isHover &&
                        "ring-2 ring-emerald-500 bg-emerald-50 dark:bg-emerald-900/20",
                      isRecent &&
                        "bg-emerald-100 dark:bg-emerald-900/30 animate-pulse",
                      draggingChunkId &&
                        !isHover &&
                        "border-dashed",
                    )}
                    onClick={() => assignByClick(c.id)}
                  >
                    <TableCell className="font-medium">
                      {c.name}
                      {isRecent && (
                        <span className="ml-2 text-xs text-emerald-600 dark:text-emerald-400">
                          ✓ 已指派
                        </span>
                      )}
                    </TableCell>
                    <TableCell className="text-right">
                      {c.chunk_count}
                    </TableCell>
                    <TableCell>
                      <Button
                        variant="ghost"
                        size="icon"
                        onClick={(e) => {
                          e.stopPropagation();
                          setPendingDelete(c);
                        }}
                      >
                        <Trash2 className="h-4 w-4 text-destructive" />
                      </Button>
                    </TableCell>
                  </TableRow>
                );
              })}
            </TableBody>
          </Table>
        </div>
        <div className="rounded bg-muted/40 p-2 text-xs text-muted-foreground space-y-1">
          <p className="font-medium text-foreground">
            操作方式（兩種選一）：
          </p>
          <p>
            <strong>拖曳法</strong>：右側 chunk 抓著拖到左側分類列
            （hover 時會發光 highlight）
          </p>
          <p>
            <strong>點擊法（鍵盤友善）</strong>：右側 chunk 點一下選取
            → 左側分類列點一下指派
          </p>
        </div>
      </div>

      {/* 右：當前 filter chunks（draggable）*/}
      <div className="space-y-2 overflow-y-auto">
        <div className="text-sm text-muted-foreground flex items-center justify-between">
          <span>
            {activeCategoryId === "uncat"
              ? "顯示前 100 個 chunks（含未分類）"
              : `顯示「${(categories ?? []).find((c) => c.id === activeCategoryId)?.name ?? "分類"}」的 chunks`}
          </span>
          {keyboardSelected && (
            <button
              type="button"
              onClick={() => setKeyboardSelected(null)}
              className="rounded bg-amber-100 dark:bg-amber-900/40 px-2 py-0.5 text-xs font-medium text-amber-700 dark:text-amber-300 hover:bg-amber-200 dark:hover:bg-amber-900/60"
              title="取消選取"
            >
              已選 1 個 chunk · 點此取消
            </button>
          )}
        </div>
        {(chunkPage?.items ?? []).map((chunk) => {
          const isSelected = keyboardSelected === chunk.id;
          const isDragging = draggingChunkId === chunk.id;
          return (
            <div
              key={chunk.id}
              draggable
              onDragStart={(e) => handleDragStart(e, chunk.id)}
              onDragEnd={handleDragEnd}
              onClick={() =>
                setKeyboardSelected((prev) =>
                  prev === chunk.id ? null : chunk.id,
                )
              }
              className={cn(
                "cursor-move transition-all rounded relative",
                isDragging && "opacity-40",
                isSelected &&
                  "ring-2 ring-amber-400 bg-amber-50/30 dark:bg-amber-900/10",
              )}
              title="拖到左側分類，或點選 chunk 後再點分類列指派"
            >
              <div className="absolute left-1 top-1 z-10 text-muted-foreground/50 pointer-events-none">
                <GripVertical className="h-3.5 w-3.5" />
              </div>
              <div className="pl-5">
                <ChunkCard chunk={chunk} mode="compact" />
              </div>
            </div>
          );
        })}
        {(chunkPage?.items ?? []).length === 0 && (
          <div className="text-muted-foreground py-8 text-center">無 chunks</div>
        )}
      </div>

      <ConfirmDangerDialog
        open={!!pendingDelete}
        onOpenChange={(o) => !o && setPendingDelete(null)}
        title={`刪除分類「${pendingDelete?.name}」？`}
        description={`此分類下 ${pendingDelete?.chunk_count ?? 0} 個 chunks 將被設為未分類（chunks 本身不刪）。`}
        confirmName={pendingDelete?.name}
        isPending={del.isPending}
        onConfirm={() => {
          if (!pendingDelete) return;
          del.mutate(pendingDelete.id, {
            onSuccess: () => setPendingDelete(null),
          });
        }}
      />
    </div>
  );
}
