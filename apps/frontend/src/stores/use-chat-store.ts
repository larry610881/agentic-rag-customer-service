import { create } from "zustand";
import type { ChatMessage, Source, ToolCallInfo } from "@/types/chat";
import type { ConversationDetail } from "@/types/conversation";

interface ChatState {
  messages: ChatMessage[];
  isStreaming: boolean;
  conversationId: string | null;
  knowledgeBaseId: string | null;
  botId: string | null;
  botName: string | null;
  toolHint: string | null;
  addUserMessage: (content: string) => void;
  startAssistantMessage: () => void;
  appendToAssistantMessage: (token: string) => void;
  finalizeAssistantMessage: (sources: Source[], toolCalls: ToolCallInfo[]) => void;
  setIsStreaming: (isStreaming: boolean) => void;
  setConversationId: (id: string) => void;
  setKnowledgeBaseId: (id: string | null) => void;
  setToolHint: (hint: string | null) => void;
  setMessageFeedback: (messageId: string, rating: "thumbs_up" | "thumbs_down" | undefined) => void;
  selectBot: (id: string, name: string) => void;
  clearBot: () => void;
  clearMessages: () => void;
  loadConversation: (detail: ConversationDetail) => void;
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
  botId: null,
  botName: null,
  toolHint: null,

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
      return { messages, toolHint: null };
    }),

  setIsStreaming: (isStreaming) => set({ isStreaming }),
  setConversationId: (id) => set({ conversationId: id }),
  setKnowledgeBaseId: (id) => set({ knowledgeBaseId: id }),
  setToolHint: (hint) => set({ toolHint: hint }),
  setMessageFeedback: (messageId, rating) =>
    set((state) => ({
      messages: state.messages.map((m) =>
        m.id === messageId ? { ...m, feedbackRating: rating } : m
      ),
    })),
  selectBot: (id, name) =>
    set({ botId: id, botName: name, messages: [], conversationId: null }),
  clearBot: () =>
    set({ botId: null, botName: null, messages: [], conversationId: null }),
  clearMessages: () =>
    set({ messages: [], conversationId: null }),

  loadConversation: (detail) =>
    set({
      conversationId: detail.id,
      messages: detail.messages.map((m) => ({
        id: m.id,
        role: m.role as "user" | "assistant",
        content: m.content,
        timestamp: m.created_at,
      })),
    }),
}));
