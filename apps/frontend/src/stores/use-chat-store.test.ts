import { describe, it, expect, beforeEach } from "vitest";
import { useChatStore } from "@/stores/use-chat-store";
import { mockSources, mockToolCalls } from "@/test/fixtures/chat";

describe("useChatStore", () => {
  beforeEach(() => {
    useChatStore.setState({
      messages: [],
      isStreaming: false,
      conversationId: null,
      knowledgeBaseId: null,
    });
  });

  it("should have empty initial state", () => {
    const state = useChatStore.getState();
    expect(state.messages).toEqual([]);
    expect(state.isStreaming).toBe(false);
    expect(state.conversationId).toBeNull();
  });

  it("should add user message", () => {
    useChatStore.getState().addUserMessage("Hello");
    const messages = useChatStore.getState().messages;
    expect(messages).toHaveLength(1);
    expect(messages[0].role).toBe("user");
    expect(messages[0].content).toBe("Hello");
  });

  it("should start and append to assistant message", () => {
    useChatStore.getState().startAssistantMessage();
    useChatStore.getState().appendToAssistantMessage("Hello");
    useChatStore.getState().appendToAssistantMessage(" world");
    const messages = useChatStore.getState().messages;
    expect(messages).toHaveLength(1);
    expect(messages[0].role).toBe("assistant");
    expect(messages[0].content).toBe("Hello world");
  });

  it("should finalize assistant message with sources and tool calls", () => {
    useChatStore.getState().startAssistantMessage();
    useChatStore.getState().appendToAssistantMessage("Answer");
    useChatStore.getState().finalizeAssistantMessage(mockSources, mockToolCalls);
    const msg = useChatStore.getState().messages[0];
    expect(msg.sources).toEqual(mockSources);
    expect(msg.tool_calls).toEqual(mockToolCalls);
  });

  it("should set streaming state", () => {
    useChatStore.getState().setIsStreaming(true);
    expect(useChatStore.getState().isStreaming).toBe(true);
  });

  it("should set conversation id", () => {
    useChatStore.getState().setConversationId("conv-1");
    expect(useChatStore.getState().conversationId).toBe("conv-1");
  });

  it("should clear messages", () => {
    useChatStore.getState().addUserMessage("Hi");
    useChatStore.getState().setConversationId("conv-1");
    useChatStore.getState().clearMessages();
    expect(useChatStore.getState().messages).toEqual([]);
    expect(useChatStore.getState().conversationId).toBeNull();
  });

  it("should set knowledge base id", () => {
    useChatStore.getState().setKnowledgeBaseId("kb-1");
    expect(useChatStore.getState().knowledgeBaseId).toBe("kb-1");
  });
});
