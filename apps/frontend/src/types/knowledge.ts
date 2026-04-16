export interface KnowledgeBase {
  id: string;
  tenant_id: string;
  name: string;
  description: string;
  ocr_mode: string;
  ocr_model: string;
  context_model: string;
  classification_model: string;
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
  has_file: boolean;
  task_progress: number | null;
  parent_id: string | null;
  page_number: number | null;
  children_count: number;
  completed_children_count?: number;
  created_at: string;
  updated_at: string;
}

export interface ChunkPreviewItem {
  id: string;
  content: string;
  context_text: string;
  chunk_index: number;
  issues: string[];
  page_number?: number | null;
  document_id?: string;
  document_filename?: string;
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

export interface BatchFailedItem {
  id: string;
  error: string;
}

export interface BatchDeleteResult {
  succeeded: string[];
  failed: BatchFailedItem[];
}

export interface BatchReprocessResult {
  tasks: Array<{ document_id: string; task_id: string }>;
  failed: BatchFailedItem[];
}

export interface ChunkCategory {
  id: string;
  kb_id: string;
  name: string;
  description: string;
  chunk_count: number;
  created_at: string;
  updated_at: string;
}

export interface TaskResponse {
  id: string;
  status: "pending" | "processing" | "completed" | "failed";
  progress: number;
  result?: Record<string, unknown>;
  error?: string;
}
