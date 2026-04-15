import { useState } from "react";
import { Loader2, Tag } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import {
  useCategories,
  useUpdateCategory,
} from "@/features/knowledge/hooks/use-categories";
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
  const updateMutation = useUpdateCategory(kbId);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editName, setEditName] = useState("");

  const handleStartEdit = (catId: string, currentName: string) => {
    setEditingId(catId);
    setEditName(currentName);
  };

  const handleSaveEdit = (catId: string) => {
    if (editName.trim()) {
      updateMutation.mutate(
        { catId, name: editName.trim() },
        { onSuccess: () => setEditingId(null) },
      );
    }
  };

  const handleCancelEdit = () => {
    setEditingId(null);
    setEditName("");
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
            <div
              key={cat.id}
              className="flex items-center justify-between rounded-md border px-3 py-2 hover:bg-muted/50 transition-colors duration-150"
            >
              {editingId === cat.id ? (
                <div className="flex items-center gap-2 flex-1">
                  <Input
                    value={editName}
                    onChange={(e) => setEditName(e.target.value)}
                    className="h-7 text-sm"
                    autoFocus
                    onKeyDown={(e) => {
                      if (e.key === "Enter") handleSaveEdit(cat.id);
                      if (e.key === "Escape") handleCancelEdit();
                    }}
                  />
                  <Button
                    variant="ghost"
                    size="sm"
                    className="h-7 text-xs"
                    onClick={() => handleSaveEdit(cat.id)}
                    disabled={updateMutation.isPending}
                  >
                    儲存
                  </Button>
                  <Button
                    variant="ghost"
                    size="sm"
                    className="h-7 text-xs"
                    onClick={handleCancelEdit}
                  >
                    取消
                  </Button>
                </div>
              ) : (
                <>
                  <span
                    className="text-sm cursor-pointer hover:underline"
                    onClick={() => handleStartEdit(cat.id, cat.name)}
                    title="點擊編輯名稱"
                  >
                    {cat.name}
                  </span>
                  <Badge variant="secondary" className="text-xs">
                    {cat.chunk_count} chunks
                  </Badge>
                </>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
