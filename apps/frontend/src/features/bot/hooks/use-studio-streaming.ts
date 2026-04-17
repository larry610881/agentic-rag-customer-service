import { useCallback, useState } from "react";
import { fetchSSE, type SSEEvent } from "@/lib/sse-client";
import { API_ENDPOINTS } from "@/lib/api-endpoints";
import { API_BASE } from "@/lib/api-config";
import { useAuthStore } from "@/stores/use-auth-store";

const SLOW_MODE_DELAY_MS = 800;

/** Phase 1: stream events 帶 node_id 後給前端的精準 source 描述 */
export type StudioSource = {
  document_name?: string;
  content_snippet?: string;
  score?: number;
  source?: string;
  [key: string]: unknown;
};

export type StudioStreamCallbacks = {
  onEvent?: (event: SSEEvent) => void;
  onTraceComplete?: (traceId: string) => void;
  /** 路由結果：worker_routing event 抵達時觸發。worker_name 對應藍圖 worker.id。 */
  onWorkerRouting?: (info: {
    worker_name: string;
    worker_llm: string;
    node_id?: string;
  }) => void;
  /** 動態 chunk：sources event 進來時，每個 source 觸發一次 */
  onChunkNode?: (toolNodeId: string, source: StudioSource, idx: number) => void;
  /** 失敗節點：error event 進來時觸發（含 node_id 對應到 trace 節點） */
  onFailedNode?: (info: { node_id: string; error_message: string }) => void;
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

      // Phase 1: 用 node_id 追蹤上一個 tool 節點，sources event 進來時對應到該 tool
      let lastToolNodeId: string | null = null;

      const handleEvent = async (event: SSEEvent) => {
        callbacks.onEvent?.(event);

        if (event.type === "tool_calls" && typeof event.node_id === "string") {
          lastToolNodeId = event.node_id;
        }

        if (
          event.type === "worker_routing" &&
          typeof event.worker_name === "string"
        ) {
          callbacks.onWorkerRouting?.({
            worker_name: event.worker_name,
            worker_llm:
              typeof event.worker_llm === "string" ? event.worker_llm : "",
            node_id:
              typeof event.node_id === "string" ? event.node_id : undefined,
          });
        }

        if (
          event.type === "sources" &&
          Array.isArray(event.sources) &&
          lastToolNodeId
        ) {
          (event.sources as StudioSource[]).forEach((src, idx) => {
            callbacks.onChunkNode?.(lastToolNodeId!, src, idx);
          });
        }

        if (event.type === "error" && typeof event.message === "string") {
          callbacks.onFailedNode?.({
            node_id:
              typeof event.node_id === "string" ? event.node_id : "",
            error_message: event.message,
          });
        }

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
