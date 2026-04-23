import { DocumentList } from "@/features/knowledge/components/document-list";
import { useDocuments } from "@/hooks/queries/use-documents";

interface DocumentsTabProps {
  kbId: string;
}

export function DocumentsTab({ kbId }: DocumentsTabProps) {
  const { data: pagedData, isLoading } = useDocuments(kbId, 1, 50);
  const documents = pagedData?.items ?? [];

  if (isLoading) {
    return <p className="text-muted-foreground">載入中...</p>;
  }

  return <DocumentList kbId={kbId} documents={documents} />;
}
