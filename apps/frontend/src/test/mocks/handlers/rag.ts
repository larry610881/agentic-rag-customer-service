import { http, HttpResponse } from "msw";
import { mockChatResponse } from "@/test/fixtures/chat";

const API_BASE = "http://localhost:8000";

export const ragHandlers = [
  http.post(`${API_BASE}/api/v1/rag/query`, () => {
    return HttpResponse.json(mockChatResponse);
  }),
  http.post(`${API_BASE}/api/v1/rag/query/stream`, () => {
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
