export const queryKeys = {
  tenants: {
    all: ["tenants"] as const,
  },
  knowledgeBases: {
    all: (tenantId: string) => ["knowledge-bases", tenantId] as const,
  },
  documents: {
    all: (kbId: string) => ["documents", kbId] as const,
  },
  tasks: {
    detail: (id: string) => ["tasks", id] as const,
  },
  chat: {
    history: (conversationId: string) =>
      ["chat", conversationId] as const,
  },
  bots: {
    all: (tenantId: string) => ["bots", tenantId] as const,
    detail: (botId: string) => ["bots", "detail", botId] as const,
  },
  conversations: {
    all: (tenantId: string) => ["conversations", tenantId] as const,
    detail: (id: string) => ["conversations", "detail", id] as const,
  },
};
