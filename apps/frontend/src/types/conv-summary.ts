export interface ConvSummaryItem {
  conversation_id: string | null;
  tenant_id: string;
  bot_id: string | null;
  summary: string | null;
  created_at: string | null;
}

export interface ConvSummaryListResponse {
  items: ConvSummaryItem[];
}

export interface ConvSummarySearchRequest {
  query: string;
  tenant_id: string;
  bot_id?: string | null;
  top_k?: number;
}

export interface ConvSummarySearchHit {
  id: string;
  score: number;
  summary: string;
  bot_id: string | null;
}

export interface ConvSummarySearchResponse {
  results: ConvSummarySearchHit[];
}
