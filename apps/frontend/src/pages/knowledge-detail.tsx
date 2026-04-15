import { useState } from "react";
import { useParams } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
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

const tabs = [
  { value: "documents", label: "文件管理" },
  { value: "categories", label: "分類總覽" },
] as const;

export default function KnowledgeDetailPage() {
  const { id } = useParams<{ id: string }>();
  const { page, setPage } = usePagination();
  const [activeTab, setActiveTab] = useState<string>("documents");

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
      <h2 className="text-2xl font-semibold">知識庫管理</h2>

      <div className="flex gap-2 border-b pb-2">
        {tabs.map((tab) => (
          <Button
            key={tab.value}
            variant="ghost"
            size="sm"
            className={cn(
              activeTab === tab.value && "bg-muted font-semibold",
            )}
            onClick={() => setActiveTab(tab.value)}
          >
            {tab.label}
          </Button>
        ))}
      </div>

      {activeTab === "documents" && (
        <>
          <UploadDropzone knowledgeBaseId={id!} />
          {isLoading && <p className="text-muted-foreground">載入文件中...</p>}
          {error && (
            <p className="text-destructive">載入文件失敗，請重試。</p>
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
        </>
      )}

      {activeTab === "categories" && (
        <CategoryList kbId={id!} documents={data?.items} />
      )}
    </div>
  );
}
