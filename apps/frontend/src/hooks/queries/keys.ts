export const queryKeys = {
  tenants: {
    all: ["tenants"] as const,
  },
  knowledgeBases: {
    all: (tenantId: string) => ["knowledge-bases", tenantId] as const,
  },
  tasks: {
    detail: (id: string) => ["tasks", id] as const,
  },
  chat: {
    history: (conversationId: string) =>
      ["chat", conversationId] as const,
  },
};
