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
  avg_chunk_length: number;
  min_chunk_length: number;
  max_chunk_length: number;
  quality_score: number;
  quality_issues: string[];
  created_at: string;
  updated_at: string;
}

export interface ChunkPreviewItem {
  id: string;
  content: string;
  chunk_index: number;
  issues: string[];
}

export interface ChunkPreviewResponse {
  chunks: ChunkPreviewItem[];
  total: number;
}

export interface DocumentQualityStat {
  document_id: string;
  filename: string;
  quality_score: number;
  negative_feedback_count: number;
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
