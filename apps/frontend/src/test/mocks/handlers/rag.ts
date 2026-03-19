import { http, HttpResponse } from "msw";
import { mockChatResponse } from "@/test/fixtures/chat";

export const ragHandlers = [
  http.post("*/api/v1/rag/query", () => {
    return HttpResponse.json(mockChatResponse);
  }),
  http.post("*/api/v1/rag/query/stream", () => {
    const encoder = new TextEncoder();
    const stream = new ReadableStream({
      start(controller) {
        controller.enqueue(
          encoder.encode('data: {"type":"token","content":"Hello"}\n\n'),
        );
        controller.enqueue(
          encoder.encode('data: {"type":"token","content":" world"}\n\n'),
        );
        controller.enqueue(
          encoder.encode('data: {"type":"done"}\n\n'),
        );
        controller.close();
      },
    });
    return new HttpResponse(stream, {
      headers: { "Content-Type": "text/event-stream" },
    });
  }),
];
