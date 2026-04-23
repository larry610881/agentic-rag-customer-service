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
      <header className="space-y-2">
        <h1 className="text-2xl font-bold">Milvus 管理</h1>
        <p className="text-sm text-muted-foreground">
          所有 collection / row count / scalar index 健康度。發現 index 為「未建」時應重建。
        </p>
        <p className="text-xs text-muted-foreground bg-muted/50 border rounded-md px-3 py-2 leading-relaxed">
          ℹ️ 本頁為 <strong>DB 層維運</strong>（對齊官方 Attu 定位）— chunk 內容
          / AI 上下文摘要 / 分類等業務編輯請到 <strong>KB Studio</strong>
          （點右側「編輯 chunks」連結直接跳轉對應 KB）。改 chunk 後系統會自動觸發
          re-embedding，無需手動處理。
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
