import { useState } from "react";
import { Plus, Trash2 } from "lucide-react";
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
  };

  const handleDropToCategory = (e: React.DragEvent, catId: string) => {
    e.preventDefault();
    const chunkId = e.dataTransfer.getData("text/chunk-id");
    if (!chunkId) return;
    assign.mutate({ catId, chunkIds: [chunkId] });
  };

  const allowDrop = (e: React.DragEvent) => {
    e.preventDefault();
    e.dataTransfer.dropEffect = "move";
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
              <TableRow
                className={
                  activeCategoryId === "uncat" ? "bg-muted/50" : "cursor-pointer"
                }
                onClick={() => setActiveCategoryId("uncat")}
              >
                <TableCell className="text-muted-foreground italic">
                  (未分類)
                </TableCell>
                <TableCell className="text-right">—</TableCell>
                <TableCell />
              </TableRow>
              {(categories ?? []).map((c) => (
                <TableRow
                  key={c.id}
                  onDragOver={allowDrop}
                  onDrop={(e) => handleDropToCategory(e, c.id)}
                  className={
                    activeCategoryId === c.id
                      ? "bg-muted/50"
                      : "cursor-pointer"
                  }
                  onClick={() => setActiveCategoryId(c.id)}
                >
                  <TableCell className="font-medium">{c.name}</TableCell>
                  <TableCell className="text-right">{c.chunk_count}</TableCell>
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
              ))}
            </TableBody>
          </Table>
        </div>
        <p className="text-xs text-muted-foreground">
          提示：右側 chunks 可拖拉到左側分類列重新指派
        </p>
      </div>

      {/* 右：當前 filter chunks（draggable）*/}
      <div className="space-y-2 overflow-y-auto">
        <div className="text-sm text-muted-foreground">
          {activeCategoryId === "uncat"
            ? "顯示前 100 個 chunks（含未分類）"
            : `顯示「${(categories ?? []).find((c) => c.id === activeCategoryId)?.name ?? "分類"}」的 chunks`}
        </div>
        {(chunkPage?.items ?? []).map((chunk) => (
          <div
            key={chunk.id}
            draggable
            onDragStart={(e) => handleDragStart(e, chunk.id)}
            className="cursor-move"
          >
            <ChunkCard chunk={chunk} mode="compact" />
          </div>
        ))}
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
