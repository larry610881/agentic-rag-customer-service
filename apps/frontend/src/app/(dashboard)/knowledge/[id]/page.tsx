"use client";

import { useParams } from "next/navigation";
import { DocumentList } from "@/features/knowledge/components/document-list";
import { UploadDropzone } from "@/features/knowledge/components/upload-dropzone";
import { useDocuments, useDeleteDocument } from "@/hooks/queries/use-documents";

export default function KnowledgeBaseDetailPage() {
  const params = useParams<{ id: string }>();

  const { data: documents, isLoading, error } = useDocuments(params.id);
  const deleteDocument = useDeleteDocument();

  const handleDelete = (docId: string) => {
    deleteDocument.mutate({ knowledgeBaseId: params.id, docId });
  };

  return (
    <div className="flex flex-col gap-6 p-6">
      <h2 className="text-2xl font-semibold">文件管理</h2>
      <UploadDropzone knowledgeBaseId={params.id} />
      {isLoading && <p className="text-muted-foreground">載入文件中...</p>}
      {error && (
        <p className="text-destructive">
          載入文件失敗，請重試。
        </p>
      )}
      {documents && (
        <DocumentList
          documents={documents}
          onDelete={handleDelete}
          isDeleting={deleteDocument.isPending}
        />
      )}
    </div>
  );
}
