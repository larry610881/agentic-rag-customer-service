export type Rating = "thumbs_up" | "thumbs_down";

export type Channel = "web" | "line" | "api";

export interface SubmitFeedbackRequest {
  conversation_id: string;
  message_id: string;
  channel: Channel;
  rating: Rating;
  user_id?: string;
  comment?: string;
  tags?: string[];
}

export interface FeedbackResponse {
  id: string;
  tenant_id: string;
  conversation_id: string;
  message_id: string;
  user_id: string | null;
  channel: Channel;
  rating: Rating;
  comment: string | null;
  tags: string[];
  created_at: string;
}

export interface FeedbackStats {
  total: number;
  thumbs_up: number;
  thumbs_down: number;
  satisfaction_rate: number;
}

export interface DailyFeedbackStat {
  date: string;
  total: number;
  positive: number;
  negative: number;
  satisfaction_pct: number;
}

export interface TagCount {
  tag: string;
  count: number;
}

export interface RetrievalQualityRecord {
  user_question: string;
  assistant_answer: string;
  retrieved_chunks: Record<string, unknown>[];
  rating: string;
  comment: string | null;
  created_at: string;
}

export interface ModelCostStat {
  model: string;
  message_count: number;
  input_tokens: number;
  output_tokens: number;
  avg_latency_ms: number;
  estimated_cost: number;
}
