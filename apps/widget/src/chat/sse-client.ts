import type { SSEEvent } from "../types";
import { authHeaders, refreshWidgetToken } from "../session";

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

  const send = async (retry: boolean): Promise<Response> => {
    const res = await fetch(url, {
      method: "POST",
      headers: await authHeaders({ "Content-Type": "application/json" }),
      body: JSON.stringify(body),
      signal: controller.signal,
    });
    if (res.status === 401 && retry) {
      await refreshWidgetToken();
      return send(false);
    }
    return res;
  };

  send(true)
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
        // 錯誤回報交給 chat-panel 的 onError（走 /widget/{code}/error，帶票）
        onError(err);
      }
    });

  return controller;
}
