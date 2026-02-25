import type { FeedbackResponse, FeedbackStats } from "@/types/feedback";

export const mockFeedback: FeedbackResponse = {
  id: "fb-1",
  tenant_id: "tenant-1",
  conversation_id: "conv-1",
  message_id: "msg-1",
  user_id: null,
  channel: "web",
  rating: "thumbs_up",
  comment: null,
  tags: [],
  created_at: "2024-03-01T10:00:00Z",
};

export const mockFeedbackList: FeedbackResponse[] = [
  mockFeedback,
  {
    id: "fb-2",
    tenant_id: "tenant-1",
    conversation_id: "conv-1",
    message_id: "msg-2",
    user_id: null,
    channel: "web",
    rating: "thumbs_down",
    comment: "答案不正確",
    tags: ["答案不正確"],
    created_at: "2024-03-01T10:05:00Z",
  },
];

export const mockFeedbackStats: FeedbackStats = {
  total: 10,
  thumbs_up: 7,
  thumbs_down: 3,
  satisfaction_rate: 70.0,
};
