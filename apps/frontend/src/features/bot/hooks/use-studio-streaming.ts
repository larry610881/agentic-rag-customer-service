import { useCallback, useState } from "react";
import { fetchSSE, type SSEEvent } from "@/lib/sse-client";
import { API_ENDPOINTS } from "@/lib/api-endpoints";
import { API_BASE } from "@/lib/api-config";
import { useAuthStore } from "@/stores/use-auth-store";

const SLOW_MODE_DELAY_MS = 800;

export type StudioStreamCallbacks = {
  onEvent?: (event: SSEEvent) => void;
  onTraceComplete?: (traceId: string) => void;
  onError?: (error: Error) => void;
};

export type SendStudioMessageOptions = {
  message: string;
  botId: string;
  conversationId?: string | null;
  slowMode?: boolean;
};

const sleep = (ms: number) =>
  new Promise<void>((resolve) => setTimeout(resolve, ms));

/**
 * Studio 專用 streaming hook — 與 chat store 解耦，只負責 push raw SSE events
 * 給 callback。動畫畫面層自行用這些事件驅動 ReactFlow 節點點亮。
 *
 * - 自動帶 identity_source: "studio" → trace.source 持久化分流
 * - slowMode: true 時每事件處理完 await 800ms，方便客戶 demo 時看清楚決策
 * - done.trace_id 觸發 onTraceComplete，讓畫面 fetch 完整 DAG 補完最終態
 */
export function useStudioStreaming(callbacks: StudioStreamCallbacks = {}) {
  const token = useAuthStore((s) => s.token);
  const [isStreaming, setIsStreaming] = useState(false);

  const sendMessage = useCallback(
    async ({
      message,
      botId,
      conversationId = null,
      slowMode = false,
    }: SendStudioMessageOptions) => {
      if (!token) return;
      setIsStreaming(true);

      const handleEvent = async (event: SSEEvent) => {
        callbacks.onEvent?.(event);
        if (event.type === "done" && typeof event.trace_id === "string") {
          callbacks.onTraceComplete?.(event.trace_id);
        }
        if (slowMode) await sleep(SLOW_MODE_DELAY_MS);
      };

      try {
        await fetchSSE(
          `${API_BASE}${API_ENDPOINTS.agent.chatStream}`,
          {
            message,
            bot_id: botId,
            conversation_id: conversationId,
            identity_source: "studio",
          },
          token,
          (event) => {
            void handleEvent(event);
          },
          (error) => {
            callbacks.onError?.(error);
            setIsStreaming(false);
          },
        );
      } catch (err) {
        if (err instanceof Error) callbacks.onError?.(err);
      } finally {
        setIsStreaming(false);
      }
    },
    [token, callbacks],
  );

  return { sendMessage, isStreaming };
}
