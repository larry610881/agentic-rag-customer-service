import type {
  ConversationSummary,
  ConversationDetail,
} from "@/types/conversation";

export const mockConversations: ConversationSummary[] = [
  {
    id: "conv-abc12345-1111",
    tenant_id: "tenant-1",
    created_at: "2024-03-01T10:00:00Z",
  },
  {
    id: "conv-def67890-2222",
    tenant_id: "tenant-1",
    created_at: "2024-03-02T14:30:00Z",
  },
];

export const mockConversationDetail: ConversationDetail = {
  id: "conv-abc12345-1111",
  tenant_id: "tenant-1",
  messages: [
    {
      id: "msg-1",
      role: "user",
      content: "How do I return an item?",
      created_at: "2024-03-01T10:00:00Z",
    },
    {
      id: "msg-2",
      role: "assistant",
      content: "You can return items within 30 days of purchase.",
      created_at: "2024-03-01T10:00:05Z",
    },
  ],
  created_at: "2024-03-01T10:00:00Z",
};
