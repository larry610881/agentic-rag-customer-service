import { useState } from "react";
import { Loader2, RefreshCw, Tag } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import {
  useCategories,
  useClassifyKb,
  useUpdateCategory,
} from "@/features/knowledge/hooks/use-categories";

type CategoryListProps = {
  kbId: string;
};

export function CategoryList({ kbId }: CategoryListProps) {
  const { data: categories, isLoading } = useCategories(kbId);
  const classifyMutation = useClassifyKb(kbId);
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
        </h3>
        <Button
          variant="outline"
          size="sm"
          onClick={() => classifyMutation.mutate()}
          disabled={classifyMutation.isPending}
        >
          {classifyMutation.isPending ? (
            <Loader2 className="h-3.5 w-3.5 animate-spin mr-1" />
          ) : (
            <RefreshCw className="h-3.5 w-3.5 mr-1" />
          )}
          {classifyMutation.isPending ? "分類中..." : "重新分類"}
        </Button>
      </div>

      {isLoading && (
        <div className="text-sm text-muted-foreground">載入中...</div>
      )}

      {!isLoading && (!categories || categories.length === 0) && (
        <div className="text-sm text-muted-foreground rounded-md border border-dashed p-4 text-center">
          尚無分類。點「重新分類」自動產生。
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
