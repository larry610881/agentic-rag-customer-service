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
  // Real-RAG 對齊（Playground 跟真實對話只差 LLM ReAct 決策層）
  score_threshold?: number;
  rerank_enabled?: boolean;
  rerank_model?: string;
  rerank_top_n?: number;
  // Issue #43 — multi-mode retrieval
  retrieval_modes?: ("raw" | "rewrite" | "hyde")[];
  query_rewrite_enabled?: boolean;
  query_rewrite_model?: string;
  query_rewrite_extra_hint?: string;
  hyde_enabled?: boolean;
  hyde_model?: string;
  hyde_extra_hint?: string;
  bot_id?: string;
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
  rewritten_query?: string;
  /** Issue #43 — 每個 retrieval mode 實際送 embed 的 query 字串 */
  mode_queries?: Record<string, string>;
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
