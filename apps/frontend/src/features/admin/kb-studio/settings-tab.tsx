interface SettingsTabProps {
  kbId: string;
}

export function SettingsTab({ kbId }: SettingsTabProps) {
  // 既有 KB 設定（embedding / context_model / classification_model）已在
  // /admin/knowledge-bases 列表的 row dialog 編輯。本 tab 暫顯示提示，
  // 完整 inline 編輯留下個 sprint（O5：統一 KB detail 資料層後一併做）
  return (
    <div className="rounded-md border bg-muted/40 p-6 text-sm text-muted-foreground">
      <p className="mb-2 font-medium">KB 模型設定</p>
      <p>
        embedding model / context model / classification model 設定請於
        <span className="px-1 font-mono">/admin/knowledge-bases</span>
        列表頁的編輯 dialog 操作（KB ID:{" "}
        <span className="font-mono">{kbId}</span>）。
      </p>
      <p className="mt-2 text-xs">
        Studio 內 inline 編輯支援預計於下個 sprint 加入（與 admin-kb-detail
        資料層統一一併處理）。
      </p>
    </div>
  );
}
