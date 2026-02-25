import type {
  DailyFeedbackStat,
  FeedbackResponse,
  FeedbackStats,
  ModelCostStat,
  RetrievalQualityRecord,
  TagCount,
} from "@/types/feedback";

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

export const mockSatisfactionTrend: DailyFeedbackStat[] = [
  { date: "2024-03-01", total: 5, positive: 4, negative: 1, satisfaction_pct: 80.0 },
  { date: "2024-03-02", total: 3, positive: 2, negative: 1, satisfaction_pct: 66.7 },
  { date: "2024-03-03", total: 4, positive: 3, negative: 1, satisfaction_pct: 75.0 },
];

export const mockTopIssues: TagCount[] = [
  { tag: "答案不正確", count: 8 },
  { tag: "不完整", count: 5 },
  { tag: "沒回答問題", count: 3 },
  { tag: "語氣不好", count: 1 },
];

export const mockRetrievalQuality: RetrievalQualityRecord[] = [
  {
    user_question: "退貨政策是什麼？",
    assistant_answer: "我們提供 30 天退貨保證。",
    retrieved_chunks: [{ content: "30 天內可退貨", score: 0.95 }],
    rating: "thumbs_down",
    comment: "資訊不完整",
    created_at: "2024-03-01T10:00:00Z",
  },
];

export const mockTokenCostStats: ModelCostStat[] = [
  {
    model: "gpt-4",
    message_count: 50,
    input_tokens: 25000,
    output_tokens: 12000,
    avg_latency_ms: 2500,
    estimated_cost: 1.85,
  },
  {
    model: "gpt-3.5-turbo",
    message_count: 120,
    input_tokens: 60000,
    output_tokens: 30000,
    avg_latency_ms: 800,
    estimated_cost: 0.135,
  },
];
