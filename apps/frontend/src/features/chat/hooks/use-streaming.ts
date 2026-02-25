"use client";

import { useCallback } from "react";
import { fetchSSE, type SSEEvent } from "@/lib/sse-client";
import { API_ENDPOINTS } from "@/lib/api-endpoints";
import { useAuthStore } from "@/stores/use-auth-store";
import { useChatStore } from "@/stores/use-chat-store";
import type { Source, ToolCallInfo } from "@/types/chat";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

const TOOL_HINTS: Record<string, string> = {
  rag_query: "\u{1f50d} 正在查詢知識庫",
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

      const handleEvent = (event: SSEEvent) => {
        switch (event.type) {
          case "token":
            setToolHint(null);
            appendToAssistantMessage(event.content as string);
            break;
          case "sources":
            sources = event.sources as Source[];
            break;
          case "tool_calls": {
            toolCalls = event.tool_calls as ToolCallInfo[];
            const toolName = toolCalls[0]?.tool_name || "";
            const hint = TOOL_HINTS[toolName];
            if (hint) {
              setToolHint(hint);
            }
            break;
          }
          case "conversation_id":
            setConversationId(event.conversation_id as string);
            break;
          case "error":
            setToolHint(null);
            appendToAssistantMessage(
              `\u26a0\ufe0f ${(event.message as string) || "發生錯誤，請稍後再試"}`,
            );
            break;
          case "done":
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
            setToolHint(null);
            setIsStreaming(false);
          },
        );
      } catch {
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
