import { useParams } from "react-router-dom";
import { CategoryList } from "@/features/knowledge/components/category-list";
import { DocumentList } from "@/features/knowledge/components/document-list";
import { UploadDropzone } from "@/features/knowledge/components/upload-dropzone";
import {
  useDocuments,
  useDeleteDocument,
  useBatchDeleteDocuments,
  useBatchReprocessDocuments,
} from "@/hooks/queries/use-documents";
import { useDocumentQualityStats } from "@/hooks/queries/use-document-quality-stats";
import { PaginationControls } from "@/components/shared/pagination-controls";
import { usePagination } from "@/hooks/use-pagination";

export default function KnowledgeDetailPage() {
  const { id } = useParams<{ id: string }>();
  const { page, setPage } = usePagination();

  const { data, isLoading, error } = useDocuments(id!, page);
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
      <CategoryList kbId={id!} />
      {isLoading && <p className="text-muted-foreground">載入文件中...</p>}
      {error && (
        <p className="text-destructive">
          載入文件失敗，請重試。
        </p>
      )}
      {data && (
        <>
          <DocumentList
            kbId={id!}
            documents={data.items}
            qualityStats={qualityStats}
            onDelete={handleDelete}
            onBatchDelete={handleBatchDelete}
            onBatchReprocess={handleBatchReprocess}
            isDeleting={deleteDocument.isPending}
            isBatchDeleting={batchDelete.isPending}
            isBatchReprocessing={batchReprocess.isPending}
          />
          <PaginationControls
            page={page}
            totalPages={data.total_pages}
            onPageChange={setPage}
          />
        </>
      )}
    </div>
  );
}
