import { create } from "zustand";
import type { ChatMessage, Source, ToolCallInfo } from "@/types/chat";

interface ChatState {
  messages: ChatMessage[];
  isStreaming: boolean;
  conversationId: string | null;
  knowledgeBaseId: string | null;
  addUserMessage: (content: string) => void;
  startAssistantMessage: () => void;
  appendToAssistantMessage: (token: string) => void;
  finalizeAssistantMessage: (sources: Source[], toolCalls: ToolCallInfo[]) => void;
  setIsStreaming: (isStreaming: boolean) => void;
  setConversationId: (id: string) => void;
  setKnowledgeBaseId: (id: string | null) => void;
  clearMessages: () => void;
}

let messageIdCounter = 0;

function nextId(): string {
  messageIdCounter += 1;
  return `msg-${messageIdCounter}`;
}

export const useChatStore = create<ChatState>((set) => ({
  messages: [],
  isStreaming: false,
  conversationId: null,
  knowledgeBaseId: null,

  addUserMessage: (content) =>
    set((state) => ({
      messages: [
        ...state.messages,
        {
          id: nextId(),
          role: "user",
          content,
          timestamp: new Date().toISOString(),
        },
      ],
    })),

  startAssistantMessage: () =>
    set((state) => ({
      messages: [
        ...state.messages,
        {
          id: nextId(),
          role: "assistant",
          content: "",
          timestamp: new Date().toISOString(),
        },
      ],
    })),

  appendToAssistantMessage: (token) =>
    set((state) => {
      const messages = [...state.messages];
      const lastMsg = messages[messages.length - 1];
      if (lastMsg && lastMsg.role === "assistant") {
        messages[messages.length - 1] = {
          ...lastMsg,
          content: lastMsg.content + token,
        };
      }
      return { messages };
    }),

  finalizeAssistantMessage: (sources, toolCalls) =>
    set((state) => {
      const messages = [...state.messages];
      const lastMsg = messages[messages.length - 1];
      if (lastMsg && lastMsg.role === "assistant") {
        messages[messages.length - 1] = {
          ...lastMsg,
          sources,
          tool_calls: toolCalls,
        };
      }
      return { messages };
    }),

  setIsStreaming: (isStreaming) => set({ isStreaming }),
  setConversationId: (id) => set({ conversationId: id }),
  setKnowledgeBaseId: (id) => set({ knowledgeBaseId: id }),
  clearMessages: () =>
    set({ messages: [], conversationId: null }),
}));
