export interface Chunk {
  id: string;
  document_id: string;
  tenant_id: string;
  content: string;
  context_text: string;
  chunk_index: number;
  category_id: string | null;
  quality_flag: string | null;
}

export interface ChunkListResponse {
  items: Chunk[];
  total: number;
  page: number;
  page_size: number;
}

export interface UpdateChunkRequest {
  content?: string;
  context_text?: string;
}

export interface RetrievalTestRequest {
  query: string;
  top_k?: number;
  include_conv_summaries?: boolean;
}

export interface RetrievalHit {
  chunk_id: string;
  content: string;
  score: number;
  source: "chunk" | "conv_summary";
  metadata: Record<string, unknown>;
}

export interface RetrievalTestResult {
  results: RetrievalHit[];
  filter_expr: string;
  query_vector_dim: number;
}

export interface KbQualitySummary {
  total_chunks: number;
  low_quality_count: number;
  avg_cohesion_score: number;
}

export interface ChunkCategory {
  id: string;
  kb_id: string;
  name: string;
  description: string | null;
  chunk_count: number;
}
