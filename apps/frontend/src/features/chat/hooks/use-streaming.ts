import { useCallback } from "react";
import { fetchSSE, type SSEEvent } from "@/lib/sse-client";
import { API_ENDPOINTS } from "@/lib/api-endpoints";
import { STREAMING_CONFIG } from "@/constants/streaming";
import { useAuthStore } from "@/stores/use-auth-store";
import { useChatStore } from "@/stores/use-chat-store";
import { getToolLabel } from "@/constants/tool-labels";
import type { Source, ToolCallInfo } from "@/types/chat";

const API_BASE = import.meta.env.VITE_API_URL || "http://localhost:8000";

const getToolHint = (toolName: string): string =>
  `\u{1f50d} ${getToolLabel(toolName)} 使用中`;

const getStatusHint = (status: string): string => {
  if (status.endsWith("_executing")) {
    const toolName = status.replace("_executing", "");
    return `\u{1f50d} ${getToolLabel(toolName)} 使用中...`;
  }
  if (status.endsWith("_done")) {
    const toolName = status.replace("_done", "");
    return `\u2705 ${getToolLabel(toolName)} 完成`;
  }
  if (status === "react_thinking") return "\u{1f9e0} AI 思考中...";
  if (status === "llm_generating") return "\u{1f3c3} 小助手努力打字中...";
  return "";
};

export function useStreaming() {
  const token = useAuthStore((s) => s.token);
  const {
    conversationId,
    botId,
    addUserMessage,
    startAssistantMessage,
    appendToAssistantMessage,
    finalizeAssistantMessage,
    setIsStreaming,
    setConversationId,
    setToolHint,
  } = useChatStore();

  const sendMessage = useCallback(
    async (message: string) => {
      if (!token) return;

      addUserMessage(message);
      startAssistantMessage();
      setIsStreaming(true);
      setToolHint(null);

      let sources: Source[] = [];
      let toolCalls: ToolCallInfo[] = [];

      // --- Throttled hint: ensure each status is visible for a minimum duration ---
      const minMs = STREAMING_CONFIG.STATUS_MIN_DISPLAY_MS;
      let lastHintTime = 0;
      let hintTimer: ReturnType<typeof setTimeout> | null = null;

      const setHintThrottled = (hint: string | null) => {
        // Clearing (null) is always immediate — tokens are already flowing
        if (hint === null) {
          if (hintTimer) {
            clearTimeout(hintTimer);
            hintTimer = null;
          }
          setToolHint(null);
          lastHintTime = 0;
          return;
        }

        const now = Date.now();
        const elapsed = now - lastHintTime;

        if (hintTimer) {
          clearTimeout(hintTimer);
          hintTimer = null;
        }

        if (elapsed >= minMs || lastHintTime === 0) {
          setToolHint(hint);
          lastHintTime = now;
        } else {
          hintTimer = setTimeout(() => {
            setToolHint(hint);
            lastHintTime = Date.now();
            hintTimer = null;
          }, minMs - elapsed);
        }
      };

      const handleEvent = (event: SSEEvent) => {
        switch (event.type) {
          case "token":
            setHintThrottled(null);
            appendToAssistantMessage(event.content as string);
            break;
          case "sources":
            sources = event.sources as Source[];
            break;
          case "tool_calls": {
            const newCalls = event.tool_calls as ToolCallInfo[];
            toolCalls = [...toolCalls, ...newCalls];
            const toolName = newCalls[0]?.tool_name || "";
            setHintThrottled(getToolHint(toolName));
            break;
          }
          case "status": {
            const statusHint = getStatusHint(event.status as string);
            if (statusHint) {
              setHintThrottled(statusHint);
            }
            break;
          }
          case "conversation_id":
            setConversationId(event.conversation_id as string);
            break;
          case "error":
            setHintThrottled(null);
            appendToAssistantMessage(
              `\u26a0\ufe0f ${(event.message as string) || "發生錯誤，請稍後再試"}`,
            );
            break;
          case "done":
            if (hintTimer) {
              clearTimeout(hintTimer);
              hintTimer = null;
            }
            finalizeAssistantMessage(sources, toolCalls);
            setIsStreaming(false);
            break;
        }
      };

      try {
        await fetchSSE(
          `${API_BASE}${API_ENDPOINTS.agent.chatStream}`,
          {
            message,
            conversation_id: conversationId,
            bot_id: botId,
          },
          token,
          handleEvent,
          (error) => {
            console.error("SSE error:", error);
            if (hintTimer) {
              clearTimeout(hintTimer);
              hintTimer = null;
            }
            setToolHint(null);
            setIsStreaming(false);
          },
        );
      } catch {
        if (hintTimer) {
          clearTimeout(hintTimer);
          hintTimer = null;
        }
        setToolHint(null);
        setIsStreaming(false);
      }
    },
    [
      token,
      conversationId,
      botId,
      addUserMessage,
      startAssistantMessage,
      appendToAssistantMessage,
      finalizeAssistantMessage,
      setIsStreaming,
      setConversationId,
      setToolHint,
    ],
  );

  return { sendMessage };
}
