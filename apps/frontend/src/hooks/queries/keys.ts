export const queryKeys = {
  tenants: {
    all: ["tenants"] as const,
  },
  knowledgeBases: {
    all: (tenantId: string) => ["knowledge-bases", tenantId] as const,
  },
  documents: {
    all: (kbId: string) => ["documents", kbId] as const,
    chunks: (kbId: string, docId: string) =>
      ["documents", kbId, docId, "chunks"] as const,
    qualityStats: (kbId: string) =>
      ["documents", kbId, "quality-stats"] as const,
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
    all: (tenantId: string, botId?: string | null) =>
      ["conversations", tenantId, botId ?? "all"] as const,
    detail: (id: string) => ["conversations", "detail", id] as const,
  },
  feedback: {
    stats: (tenantId: string) => ["feedback", "stats", tenantId] as const,
    byConversation: (conversationId: string) =>
      ["feedback", "conversation", conversationId] as const,
    list: (tenantId: string) => ["feedback", "list", tenantId] as const,
    trend: (tenantId: string, days: number) =>
      ["feedback", "trend", tenantId, days] as const,
    topIssues: (tenantId: string, days: number) =>
      ["feedback", "topIssues", tenantId, days] as const,
    retrievalQuality: (tenantId: string, days: number) =>
      ["feedback", "retrievalQuality", tenantId, days] as const,
    tokenCost: (tenantId: string, days: number) =>
      ["feedback", "tokenCost", tenantId, days] as const,
  },
  providerSettings: {
    all: ["provider-settings"] as const,
    byType: (type: string) =>
      ["provider-settings", type] as const,
    enabledModels: ["provider-settings", "enabled-models"] as const,
    modelRegistry: ["provider-settings", "model-registry"] as const,
  },
  logs: {
    all: (filters?: object) => ["logs", filters ?? {}] as const,
    detail: (requestId: string) => ["logs", "detail", requestId] as const,
  },
  admin: {
    knowledgeBases: ["admin", "knowledge-bases"] as const,
    bots: ["admin", "bots"] as const,
  },
  systemPrompts: {
    all: ["system-prompts"] as const,
  },
  mcpRegistry: {
    all: ["mcp-registry"] as const,
    detail: (id: string) => ["mcp-registry", id] as const,
  },
  observability: {
    traces: (filters?: object) => ["observability", "traces", filters ?? {}] as const,
    evals: (filters?: object) => ["observability", "evals", filters ?? {}] as const,
    tokenUsage: (days: number) => ["observability", "token-usage", days] as const,
    diagnosticRules: ["observability", "diagnostic-rules"] as const,
  },
};
