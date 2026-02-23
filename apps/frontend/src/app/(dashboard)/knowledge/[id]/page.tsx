"use client";

import { useState } from "react";
import { useParams } from "next/navigation";
import { DocumentList } from "@/features/knowledge/components/document-list";
import { UploadDropzone } from "@/features/knowledge/components/upload-dropzone";
import { UploadProgress } from "@/features/knowledge/components/upload-progress";
import { mockDocuments } from "@/test/fixtures/knowledge";

export default function KnowledgeBaseDetailPage() {
  const params = useParams<{ id: string }>();
  const [activeTaskId, setActiveTaskId] = useState<string | null>(null);

  // TODO: Replace with real API query when backend endpoint is ready
  const documents = mockDocuments.filter(
    (d) => d.knowledge_base_id === params.id,
  );

  return (
    <div className="flex flex-col gap-6 p-6">
      <h2 className="text-2xl font-semibold">Documents</h2>
      <UploadDropzone
        knowledgeBaseId={params.id}
        onUploadStarted={setActiveTaskId}
      />
      {activeTaskId && <UploadProgress taskId={activeTaskId} />}
      <DocumentList documents={documents} />
    </div>
  );
}
