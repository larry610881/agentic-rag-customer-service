import { http, HttpResponse } from "msw";
import {
  mockFeedback,
  mockFeedbackList,
  mockFeedbackStats,
} from "@/test/fixtures/feedback";

const API_BASE = "http://localhost:8000";

export const feedbackHandlers = [
  http.post(`${API_BASE}/api/v1/feedback`, async ({ request }) => {
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
  http.get(`${API_BASE}/api/v1/feedback`, () => {
    return HttpResponse.json(mockFeedbackList);
  }),
  http.get(`${API_BASE}/api/v1/feedback/stats`, () => {
    return HttpResponse.json(mockFeedbackStats);
  }),
  http.get(`${API_BASE}/api/v1/feedback/conversation/:conversationId`, () => {
    return HttpResponse.json(mockFeedbackList);
  }),
];
