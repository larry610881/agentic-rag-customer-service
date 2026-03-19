import { http, HttpResponse } from "msw";
import {
  mockFeedback,
  mockFeedbackList,
  mockFeedbackStats,
  mockSatisfactionTrend,
  mockTopIssues,
  mockRetrievalQuality,
  mockTokenCostStats,
} from "@/test/fixtures/feedback";

export const feedbackHandlers = [
  http.post("*/api/v1/feedback", async ({ request }) => {
    const body = (await request.json()) as Record<string, unknown>;
    return HttpResponse.json(
      {
        ...mockFeedback,
        id: "fb-new",
        message_id: body.message_id as string,
        rating: body.rating as string,
        comment: (body.comment as string) || null,
        tags: (body.tags as string[]) || [],
        created_at: new Date().toISOString(),
      },
      { status: 201 },
    );
  }),
  http.get("*/api/v1/feedback", () => {
    return HttpResponse.json(mockFeedbackList);
  }),
  http.get("*/api/v1/feedback/stats", () => {
    return HttpResponse.json(mockFeedbackStats);
  }),
  http.get("*/api/v1/feedback/conversation/:conversationId", () => {
    return HttpResponse.json(mockFeedbackList);
  }),
  http.patch("*/api/v1/feedback/:feedbackId/tags", () => {
    return HttpResponse.json({ status: "ok" });
  }),
  http.get("*/api/v1/feedback/analysis/satisfaction-trend", () => {
    return HttpResponse.json(mockSatisfactionTrend);
  }),
  http.get("*/api/v1/feedback/analysis/top-issues", () => {
    return HttpResponse.json(mockTopIssues);
  }),
  http.get("*/api/v1/feedback/analysis/retrieval-quality", () => {
    return HttpResponse.json(mockRetrievalQuality);
  }),
  http.get("*/api/v1/feedback/analysis/token-cost", () => {
    return HttpResponse.json(mockTokenCostStats);
  }),
];
