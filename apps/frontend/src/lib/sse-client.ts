export type SSEEvent = { type: string; [key: string]: unknown };

export async function fetchSSE(
  url: string,
  body: unknown,
  token: string,
  onEvent: (event: SSEEvent) => void,
  onError?: (error: Error) => void,
): Promise<void> {
  const res = await fetch(url, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify(body),
  });

  if (!res.ok) {
    throw new Error(`SSE request failed: ${res.status}`);
  }

  const reader = res.body?.getReader();
  if (!reader) {
    throw new Error("No response body");
  }

  const decoder = new TextDecoder();
  let buffer = "";

  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split("\n");
      buffer = lines.pop() || "";
      for (const line of lines) {
        if (line.startsWith("data: ")) {
          try {
            const data = JSON.parse(line.slice(6));
            onEvent(data);
          } catch {
            /* skip malformed */
          }
        }
      }
    }
  } catch (error) {
    if (onError && error instanceof Error) {
      onError(error);
    } else {
      throw error;
    }
  }
}
