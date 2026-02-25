import { http, HttpResponse } from "msw";
import {
  mockConversations,
  mockConversationDetail,
} from "@/test/fixtures/conversation";

const API_BASE = "http://localhost:8000";

export const conversationHandlers = [
  http.get(`${API_BASE}/api/v1/conversations`, ({ request }) => {
    const url = new URL(request.url);
    const botId = url.searchParams.get("bot_id");
    if (botId) {
      const filtered = mockConversations.filter((c) => c.bot_id === botId);
      return HttpResponse.json(filtered);
    }
    return HttpResponse.json(mockConversations);
  }),
  http.get(
    `${API_BASE}/api/v1/conversations/:conversationId`,
    ({ params }) => {
      if (params.conversationId === mockConversationDetail.id) {
        return HttpResponse.json(mockConversationDetail);
      }
      return new HttpResponse(null, { status: 404 });
    },
  ),
];
