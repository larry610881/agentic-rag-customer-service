import { http, HttpResponse } from "msw";
import { mockChatResponse } from "@/test/fixtures/chat";

const API_BASE = "http://localhost:8000";

export const agentHandlers = [
  http.post(`${API_BASE}/api/v1/agent/chat`, () => {
    return HttpResponse.json(mockChatResponse);
  }),
  http.post(`${API_BASE}/api/v1/agent/chat/stream`, () => {
    const encoder = new TextEncoder();
    const stream = new ReadableStream({
      start(controller) {
        controller.enqueue(
          encoder.encode(
            'data: {"type":"token","content":"Based on"}\n\n',
          ),
        );
        controller.enqueue(
          encoder.encode(
            'data: {"type":"token","content":" the information"}\n\n',
          ),
        );
        controller.enqueue(
          encoder.encode(
            'data: {"type":"sources","sources":[{"document_name":"faq.pdf","content_snippet":"Returns within 30 days","score":0.95}]}\n\n',
          ),
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
