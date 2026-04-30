import { DocumentList } from "@/features/knowledge/components/document-list";
import { UploadDropzone } from "@/features/knowledge/components/upload-dropzone";
import { useDocuments } from "@/hooks/queries/use-documents";

interface DocumentsTabProps {
  kbId: string;
}

export function DocumentsTab({ kbId }: DocumentsTabProps) {
  const { data: pagedData, isLoading } = useDocuments(kbId, 1, 50);
  const documents = pagedData?.items ?? [];

  return (
    // pb-24：scroll 到底時保留底部空白緩衝，避免 last row 卡在 viewport 邊緣
    <div className="space-y-4 pb-24">
      <UploadDropzone knowledgeBaseId={kbId} />
      {isLoading ? (
        <p className="text-muted-foreground">載入中...</p>
      ) : (
        // admin 端 → chunk drill-down 編輯打開：點「查看分塊」就可改 content / 刪 / re-embed
        <DocumentList kbId={kbId} documents={documents} chunkEditable />
      )}
    </div>
  );
}
