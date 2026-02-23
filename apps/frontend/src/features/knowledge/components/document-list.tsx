"use client";

import { Badge } from "@/components/ui/badge";
import type { DocumentResponse } from "@/types/knowledge";

interface DocumentListProps {
  documents: DocumentResponse[];
}

function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function statusVariant(status: DocumentResponse["status"]) {
  switch (status) {
    case "completed":
      return "default" as const;
    case "processing":
      return "secondary" as const;
    case "pending":
      return "outline" as const;
    case "failed":
      return "destructive" as const;
  }
}

export function DocumentList({ documents }: DocumentListProps) {
  if (documents.length === 0) {
    return (
      <p className="text-muted-foreground">No documents uploaded yet.</p>
    );
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b text-left">
            <th className="px-4 py-2 font-medium">File Name</th>
            <th className="px-4 py-2 font-medium">Size</th>
            <th className="px-4 py-2 font-medium">Status</th>
            <th className="px-4 py-2 font-medium">Uploaded</th>
          </tr>
        </thead>
        <tbody>
          {documents.map((doc) => (
            <tr key={doc.id} className="border-b">
              <td className="px-4 py-2">{doc.file_name}</td>
              <td className="px-4 py-2">{formatFileSize(doc.file_size)}</td>
              <td className="px-4 py-2">
                <Badge variant={statusVariant(doc.status)}>{doc.status}</Badge>
              </td>
              <td className="px-4 py-2">
                {new Date(doc.created_at).toLocaleDateString()}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
