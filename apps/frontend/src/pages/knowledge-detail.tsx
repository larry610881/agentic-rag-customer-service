import { useParams } from "react-router-dom";
import { DocumentList } from "@/features/knowledge/components/document-list";
import { UploadDropzone } from "@/features/knowledge/components/upload-dropzone";
import {
  useDocuments,
  useDeleteDocument,
  useBatchDeleteDocuments,
  useBatchReprocessDocuments,
} from "@/hooks/queries/use-documents";
import { useDocumentQualityStats } from "@/hooks/queries/use-document-quality-stats";

export default function KnowledgeDetailPage() {
  const { id } = useParams<{ id: string }>();

  const { data: documents, isLoading, error } = useDocuments(id!);
  const { data: qualityStats } = useDocumentQualityStats(id!);
  const deleteDocument = useDeleteDocument();
  const batchDelete = useBatchDeleteDocuments();
  const batchReprocess = useBatchReprocessDocuments();

  const handleDelete = (docId: string) => {
    deleteDocument.mutate({ knowledgeBaseId: id!, docId });
  };

  const handleBatchDelete = (docIds: string[]) => {
    batchDelete.mutate({ knowledgeBaseId: id!, docIds });
  };

  const handleBatchReprocess = (docIds: string[]) => {
    batchReprocess.mutate({ knowledgeBaseId: id!, docIds });
  };

  return (
    <div className="flex flex-col gap-6 p-6">
      <h2 className="text-2xl font-semibold">文件管理</h2>
      <UploadDropzone knowledgeBaseId={id!} />
      {isLoading && <p className="text-muted-foreground">載入文件中...</p>}
      {error && (
        <p className="text-destructive">
          載入文件失敗，請重試。
        </p>
      )}
      {documents && (
        <DocumentList
          kbId={id!}
          documents={documents}
          qualityStats={qualityStats}
          onDelete={handleDelete}
          onBatchDelete={handleBatchDelete}
          onBatchReprocess={handleBatchReprocess}
          isDeleting={deleteDocument.isPending}
          isBatchDeleting={batchDelete.isPending}
          isBatchReprocessing={batchReprocess.isPending}
        />
      )}
    </div>
  );
}
