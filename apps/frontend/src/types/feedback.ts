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
