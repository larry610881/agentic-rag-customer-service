import { useState } from "react";
import {
  useMilvusCollections,
  useRebuildIndex,
} from "@/hooks/queries/use-milvus";
import { CollectionTable } from "@/features/admin/milvus/collection-table";
import { ConfirmDangerDialog } from "@/components/ui/confirm-danger-dialog";

export default function AdminMilvusPage() {
  const { data, isLoading, error } = useMilvusCollections();
  const rebuild = useRebuildIndex();
  const [pendingRebuild, setPendingRebuild] = useState<string | null>(null);

  const collections = data ?? [];

  return (
    <div className="space-y-4">
      <header>
        <h1 className="text-2xl font-bold">Milvus 管理</h1>
        <p className="text-sm text-muted-foreground">
          所有 collection / row count / scalar index 健康度。發現 index 為「未建」時應重建。
        </p>
      </header>

      {isLoading && <p className="text-muted-foreground">載入中...</p>}
      {error && (
        <p className="text-destructive">載入失敗：{(error as Error).message}</p>
      )}
      {!isLoading && (
        <CollectionTable
          collections={collections}
          rebuildingName={rebuild.isPending ? pendingRebuild : null}
          onRebuildIndex={(name) => setPendingRebuild(name)}
        />
      )}

      <ConfirmDangerDialog
        open={!!pendingRebuild}
        onOpenChange={(o) => !o && setPendingRebuild(null)}
        title={`重建 collection 「${pendingRebuild}」 index？`}
        description="重建期間 collection 將短暫不可服務搜尋（約 3 秒）。建議於離峰時段執行。"
        confirmLabel="開始重建"
        isPending={rebuild.isPending}
        onConfirm={() => {
          if (!pendingRebuild) return;
          rebuild.mutate(pendingRebuild, {
            onSettled: () => setPendingRebuild(null),
          });
        }}
      />
    </div>
  );
}
