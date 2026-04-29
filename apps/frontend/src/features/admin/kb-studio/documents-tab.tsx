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
    <div className="space-y-4">
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
