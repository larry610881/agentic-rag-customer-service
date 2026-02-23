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
  knowledge_base_id: string;
  file_name: string;
  file_size: number;
  status: "pending" | "processing" | "completed" | "failed";
  created_at: string;
}

export interface UploadDocumentResponse {
  document_id: string;
  task_id: string;
}

export interface TaskResponse {
  id: string;
  status: "pending" | "processing" | "completed" | "failed";
  progress: number;
  result?: Record<string, unknown>;
  error?: string;
}
