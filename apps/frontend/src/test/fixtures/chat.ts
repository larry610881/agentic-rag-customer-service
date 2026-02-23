import type { ChatMessage, ChatResponse, Source, ToolCallInfo } from "@/types/chat";

export const mockSources: Source[] = [
  {
    document_name: "product-guide.pdf",
    content_snippet: "The product supports multiple languages...",
    score: 0.95,
  },
  {
    document_name: "faq.pdf",
    content_snippet: "Returns are accepted within 30 days...",
    score: 0.87,
  },
];

export const mockToolCalls: ToolCallInfo[] = [
  {
    tool_name: "OrderLookup",
    reasoning: "Looking up order status for the customer",
  },
  {
    tool_name: "ProductSearch",
    reasoning: "Searching for product information",
  },
];

export const mockChatResponse: ChatResponse = {
  answer: "Based on the information I found, returns are accepted within 30 days.",
  conversation_id: "conv-123",
  tool_calls: mockToolCalls,
  sources: mockSources,
};

export const mockMessages: ChatMessage[] = [
  {
    id: "msg-1",
    role: "user",
    content: "What is the return policy?",
    timestamp: "2024-01-01T10:00:00Z",
  },
  {
    id: "msg-2",
    role: "assistant",
    content: "Based on the information I found, returns are accepted within 30 days.",
    sources: mockSources,
    tool_calls: mockToolCalls,
    timestamp: "2024-01-01T10:00:01Z",
  },
];
