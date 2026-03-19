import { http, HttpResponse } from "msw";
import {
  mockConversations,
  mockConversationDetail,
} from "@/test/fixtures/conversation";

export const conversationHandlers = [
  http.get("*/api/v1/conversations", ({ request }) => {
    const url = new URL(request.url);
    const botId = url.searchParams.get("bot_id");
    const items = botId
      ? mockConversations.filter((c) => c.bot_id === botId)
      : mockConversations;
    return HttpResponse.json({
      items,
      total: items.length,
      page: 1,
      page_size: 20,
      total_pages: 1,
    });
  }),
  http.get(
    "*/api/v1/conversations/:conversationId",
    ({ params }) => {
      if (params.conversationId === mockConversationDetail.id) {
        return HttpResponse.json(mockConversationDetail);
      }
      return new HttpResponse(null, { status: 404 });
    },
  ),
];
