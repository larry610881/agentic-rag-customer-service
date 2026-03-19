import { http, HttpResponse } from "msw";
import { mockBots, mockBot } from "@/test/fixtures/bot";

export const botHandlers = [
  http.get("*/api/v1/bots", () => {
    return HttpResponse.json({
      items: mockBots,
      total: mockBots.length,
      page: 1,
      page_size: 20,
      total_pages: 1,
    });
  }),
  http.get("*/api/v1/bots/:botId", ({ params }) => {
    const bot = mockBots.find((b) => b.id === params.botId);
    if (!bot) {
      return new HttpResponse(null, { status: 404 });
    }
    return HttpResponse.json(bot);
  }),
  http.post("*/api/v1/bots", async ({ request }) => {
    const body = (await request.json()) as Record<string, unknown>;
    return HttpResponse.json(
      {
        ...mockBot,
        id: "bot-new",
        name: body.name as string,
        description: (body.description as string) || "",
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
      },
      { status: 201 },
    );
  }),
  http.put("*/api/v1/bots/:botId", async ({ request, params }) => {
    const body = (await request.json()) as Record<string, unknown>;
    const existing = mockBots.find((b) => b.id === params.botId);
    if (!existing) {
      return new HttpResponse(null, { status: 404 });
    }
    return HttpResponse.json({
      ...existing,
      ...body,
      updated_at: new Date().toISOString(),
    });
  }),
  http.delete("*/api/v1/bots/:botId", () => {
    return new HttpResponse(null, { status: 204 });
  }),
];
