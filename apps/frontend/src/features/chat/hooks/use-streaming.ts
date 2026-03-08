import { useCallback } from "react";
import { fetchSSE, type SSEEvent } from "@/lib/sse-client";
import { API_ENDPOINTS } from "@/lib/api-endpoints";
import { useAuthStore } from "@/stores/use-auth-store";
import { useChatStore } from "@/stores/use-chat-store";
import type { Source, ToolCallInfo } from "@/types/chat";

const API_BASE = import.meta.env.VITE_API_URL || "http://localhost:8000";

const getToolHint = (toolName: string): string => {
  const hints: Record<string, string> = {
    rag_query: "\u{1f50d} 正在查詢知識庫",
  };
  return hints[toolName] || `\u{1f527} 正在執行 ${toolName}`;
};

const getStatusHint = (status: string): string => {
  if (status.endsWith("_executing")) {
    const toolName = status.replace("_executing", "");
    const toolLabels: Record<string, string> = {
      rag_query: "知識庫",
    };
    const label = toolLabels[toolName] || toolName;
    return `\u{1f50d} 正在執行 ${label}...`;
  }
  if (status.endsWith("_done")) {
    const toolName = status.replace("_done", "");
    const toolLabels: Record<string, string> = {
      rag_query: "知識庫查詢",
    };
    const label = toolLabels[toolName] || toolName;
    return `\u2705 ${label} 完成！`;
  }
  // Legacy status hints
  if (status === "llm_generating") return "\u270d\ufe0f 小助手努力打字中...";
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
            setToolHint(getToolHint(toolName));
            break;
          }
          case "status": {
            const statusHint = getStatusHint(event.status as string);
            if (statusHint) {
              setToolHint(statusHint);
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
