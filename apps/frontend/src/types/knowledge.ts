export interface KnowledgeBase {
  id: string;
  tenant_id: string;
  name: string;
  description: string;
  document_count: number;
  created_at: string;
  updated_at: string;
}

export interface DocumentResponse {
  id: string;
  kb_id: string;
  tenant_id: string;
  filename: string;
  content_type: string;
  status: "pending" | "processing" | "processed" | "failed";
  chunk_count: number;
  created_at: string;
  updated_at: string;
}

export interface UploadDocumentResponse {
  document: DocumentResponse;
  task_id: string;
}

export interface TaskResponse {
  id: string;
  status: "pending" | "processing" | "completed" | "failed";
  progress: number;
  result?: Record<string, unknown>;
  error?: string;
}
