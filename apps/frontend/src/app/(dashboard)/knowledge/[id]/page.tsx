"use client";

import { useState } from "react";
import { useParams } from "next/navigation";
import { DocumentList } from "@/features/knowledge/components/document-list";
import { UploadDropzone } from "@/features/knowledge/components/upload-dropzone";
import { UploadProgress } from "@/features/knowledge/components/upload-progress";
import { useDocuments, useDeleteDocument } from "@/hooks/queries/use-documents";

export default function KnowledgeBaseDetailPage() {
  const params = useParams<{ id: string }>();
  const [activeTaskId, setActiveTaskId] = useState<string | null>(null);

  const { data: documents, isLoading, error } = useDocuments(params.id);
  const deleteDocument = useDeleteDocument();

  const handleDelete = (docId: string) => {
    deleteDocument.mutate({ knowledgeBaseId: params.id, docId });
  };

  return (
    <div className="flex flex-col gap-6 p-6">
      <h2 className="text-2xl font-semibold">Documents</h2>
      <UploadDropzone
        knowledgeBaseId={params.id}
        onUploadStarted={setActiveTaskId}
      />
      {activeTaskId && <UploadProgress taskId={activeTaskId} />}
      {isLoading && <p className="text-muted-foreground">Loading documents...</p>}
      {error && (
        <p className="text-destructive">
          Failed to load documents. Please try again.
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
