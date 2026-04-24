import { create } from "zustand";
import type { ChatMessage, ContactCard, Source, ToolCallInfo } from "@/types/chat";
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
  resetAssistantContent: () => void;
  finalizeAssistantMessage: (
    sources: Source[],
    toolCalls: ToolCallInfo[],
    contact?: ContactCard,
  ) => void;
  setIsStreaming: (isStreaming: boolean) => void;
  setConversationId: (id: string) => void;
  setKnowledgeBaseId: (id: string | null) => void;
  setToolHint: (hint: string | null) => void;
  setAssistantMessageId: (id: string) => void;
  /** Sprint A++ Guard UX: Studio 收到 guard_blocked event 時調用 */
  setAssistantGuardBlocked: (
    blockType: "input" | "output",
    ruleMatched: string | null,
  ) => void;
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

  resetAssistantContent: () =>
    set((state) => {
      const messages = [...state.messages];
      const lastMsg = messages[messages.length - 1];
      if (lastMsg && lastMsg.role === "assistant") {
        messages[messages.length - 1] = { ...lastMsg, content: "" };
      }
      return { messages };
    }),

  finalizeAssistantMessage: (sources, toolCalls, contact) =>
    set((state) => {
      const messages = [...state.messages];
      const lastMsg = messages[messages.length - 1];
      if (lastMsg && lastMsg.role === "assistant") {
        messages[messages.length - 1] = {
          ...lastMsg,
          sources,
          tool_calls: toolCalls,
          ...(contact ? { contact } : {}),
        };
      }
      return { messages, toolHint: null };
    }),

  setIsStreaming: (isStreaming) => set({ isStreaming }),
  setConversationId: (id) => set({ conversationId: id }),
  setKnowledgeBaseId: (id) => set({ knowledgeBaseId: id }),
  setToolHint: (hint) => set({ toolHint: hint }),
  setAssistantMessageId: (id) =>
    set((state) => {
      const messages = [...state.messages];
      const lastMsg = messages[messages.length - 1];
      if (lastMsg && lastMsg.role === "assistant") {
        messages[messages.length - 1] = { ...lastMsg, id };
      }
      return { messages };
    }),
  setAssistantGuardBlocked: (blockType, ruleMatched) =>
    set((state) => {
      const messages = [...state.messages];
      const lastMsg = messages[messages.length - 1];
      if (lastMsg && lastMsg.role === "assistant") {
        messages[messages.length - 1] = {
          ...lastMsg,
          guardBlocked: blockType,
          guardRuleMatched: ruleMatched ?? undefined,
        };
      }
      return { messages };
    }),
  setMessageFeedback: (messageId, rating) =>
    set((state) => ({
      messages: state.messages.map((m) =>
        m.id === messageId ? { ...m, feedbackRating: rating } : m
      ),
    })),
  selectBot: (id, name) =>
    set({
      botId: id,
      botName: name,
      messages: [],
      conversationId: null,
    }),
  clearBot: () =>
    set({
      botId: null,
      botName: null,
      messages: [],
      conversationId: null,
    }),
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
        contact: m.structured_content?.contact ?? undefined,
        sources: m.structured_content?.sources ?? undefined,
      })),
    }),
}));
