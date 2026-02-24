"use client";

import { useCallback } from "react";
import { fetchSSE, type SSEEvent } from "@/lib/sse-client";
import { API_ENDPOINTS } from "@/lib/api-endpoints";
import { useAuthStore } from "@/stores/use-auth-store";
import { useChatStore } from "@/stores/use-chat-store";
import type { Source, ToolCallInfo } from "@/types/chat";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

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
  } = useChatStore();

  const sendMessage = useCallback(
    async (message: string) => {
      if (!token) return;

      addUserMessage(message);
      startAssistantMessage();
      setIsStreaming(true);

      let sources: Source[] = [];
      let toolCalls: ToolCallInfo[] = [];

      const handleEvent = (event: SSEEvent) => {
        switch (event.type) {
          case "token":
            appendToAssistantMessage(event.content as string);
            break;
          case "sources":
            sources = event.sources as Source[];
            break;
          case "tool_calls":
            toolCalls = event.tool_calls as ToolCallInfo[];
            break;
          case "conversation_id":
            setConversationId(event.conversation_id as string);
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
            setIsStreaming(false);
          },
        );
      } catch {
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
    ],
  );

  return { sendMessage };
}
