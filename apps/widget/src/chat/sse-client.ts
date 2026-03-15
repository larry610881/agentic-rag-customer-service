import type { SSEEvent } from "../types";
import { getVisitorId } from "../visitor";

/**
 * POST-based SSE client.
 * Uses fetch + ReadableStream to parse server-sent events.
 */
export function streamChat(
  url: string,
  body: { message: string; conversation_id?: string | null },
  onEvent: (event: SSEEvent) => void,
  onError: (err: Error) => void,
): AbortController {
  const controller = new AbortController();

  fetch(url, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-Visitor-Id": getVisitorId(),
    },
    body: JSON.stringify(body),
    signal: controller.signal,
  })
    .then((res) => {
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      if (!res.body) throw new Error("No response body");

      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";

      function read(): void {
        reader.read().then(({ done, value }) => {
          if (done) return;
          buffer += decoder.decode(value, { stream: true });
          const lines = buffer.split("\n");
          buffer = lines.pop() ?? "";

          for (const line of lines) {
            if (!line.startsWith("data: ")) continue;
            try {
              const event: SSEEvent = JSON.parse(line.substring(6));
              onEvent(event);
            } catch {
              // skip malformed JSON
            }
          }
          read();
        });
      }
      read();
    })
    .catch((err: Error) => {
      if (err.name !== "AbortError") {
        // Report to error tracking
        fetch(`${url.replace(/\/api\/.*$/, "")}/api/v1/error-events`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            source: "widget",
            error_type: "SSEError",
            message: err.message,
            path: window.location.pathname,
            user_agent: navigator.userAgent,
          }),
        }).catch(() => {});
        onError(err);
      }
    });

  return controller;
}
