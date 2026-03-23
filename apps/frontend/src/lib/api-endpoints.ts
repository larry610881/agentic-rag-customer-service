export const API_ENDPOINTS = {
  auth: {
    login: "/api/v1/auth/login",
    refresh: "/api/v1/auth/refresh",
  },
  tenants: {
    list: "/api/v1/tenants",
    create: "/api/v1/tenants",
    config: (id: string) => `/api/v1/tenants/${id}/config`,
    agentModes: (id: string) => `/api/v1/tenants/${id}/agent-modes`,
  },
  knowledgeBases: {
    list: "/api/v1/knowledge-bases",
    create: "/api/v1/knowledge-bases",
    delete: (id: string) => `/api/v1/knowledge-bases/${id}`,
  },
  documents: {
    list: (kbId: string) => `/api/v1/knowledge-bases/${kbId}/documents`,
    upload: (kbId: string) => `/api/v1/knowledge-bases/${kbId}/documents`,
    delete: (kbId: string, docId: string) =>
      `/api/v1/knowledge-bases/${kbId}/documents/${docId}`,
    chunks: (kbId: string, docId: string) =>
      `/api/v1/knowledge-bases/${kbId}/documents/${docId}/chunks`,
    reprocess: (kbId: string, docId: string) =>
      `/api/v1/knowledge-bases/${kbId}/documents/${docId}/reprocess`,
    qualityStats: (kbId: string) =>
      `/api/v1/knowledge-bases/${kbId}/documents/quality-stats`,
    batchDelete: (kbId: string) =>
      `/api/v1/knowledge-bases/${kbId}/documents/batch-delete`,
    batchReprocess: (kbId: string) =>
      `/api/v1/knowledge-bases/${kbId}/documents/batch-reprocess`,
    view: (kbId: string, docId: string) =>
      `/api/v1/knowledge-bases/${kbId}/documents/${docId}/view`,
  },
  tasks: {
    detail: (id: string) => `/api/v1/tasks/${id}`,
  },
  rag: {
    query: "/api/v1/rag/query",
    queryStream: "/api/v1/rag/query/stream",
  },
  agent: {
    chat: "/api/v1/agent/chat",
    chatStream: "/api/v1/agent/chat/stream",
  },
  bots: {
    list: "/api/v1/bots",
    create: "/api/v1/bots",
    detail: (id: string) => `/api/v1/bots/${id}`,
    update: (id: string) => `/api/v1/bots/${id}`,
    delete: (id: string) => `/api/v1/bots/${id}`,
  },
  conversations: {
    list: (botId?: string | null) =>
      botId ? `/api/v1/conversations?bot_id=${botId}` : "/api/v1/conversations",
    detail: (id: string) => `/api/v1/conversations/${id}`,
  },
  feedback: {
    submit: "/api/v1/feedback",
    list: "/api/v1/feedback",
    stats: "/api/v1/feedback/stats",
    byConversation: (conversationId: string) =>
      `/api/v1/feedback/conversation/${conversationId}`,
    updateTags: (feedbackId: string) =>
      `/api/v1/feedback/${feedbackId}/tags`,
    satisfactionTrend: "/api/v1/feedback/analysis/satisfaction-trend",
    topIssues: "/api/v1/feedback/analysis/top-issues",
    retrievalQuality: "/api/v1/feedback/analysis/retrieval-quality",
    tokenCost: "/api/v1/feedback/analysis/token-cost",
  },
  providerSettings: {
    list: "/api/v1/settings/providers",
    create: "/api/v1/settings/providers",
    detail: (id: string) => `/api/v1/settings/providers/${id}`,
    update: (id: string) => `/api/v1/settings/providers/${id}`,
    delete: (id: string) => `/api/v1/settings/providers/${id}`,
    testConnection: (id: string) =>
      `/api/v1/settings/providers/${id}/test-connection`,
    enabledModels: "/api/v1/settings/providers/enabled-models",
    modelRegistry: "/api/v1/settings/providers/model-registry",
  },
  logs: {
    list: "/api/v1/logs",
    detail: (requestId: string) => `/api/v1/logs/${requestId}`,
  },
  mcp: {
    discover: "/api/v1/mcp/discover",
  },
  mcpRegistry: {
    list: "/api/v1/mcp-servers",
    create: "/api/v1/mcp-servers",
    detail: (id: string) => `/api/v1/mcp-servers/${id}`,
    update: (id: string) => `/api/v1/mcp-servers/${id}`,
    delete: (id: string) => `/api/v1/mcp-servers/${id}`,
    discover: "/api/v1/mcp-servers/discover",
    testConnection: (id: string) => `/api/v1/mcp-servers/${id}/test-connection`,
  },
  adminUsers: {
    list: "/api/v1/admin/users",
    create: "/api/v1/admin/users",
    detail: (id: string) => `/api/v1/admin/users/${id}`,
    update: (id: string) => `/api/v1/admin/users/${id}`,
    delete: (id: string) => `/api/v1/admin/users/${id}`,
    resetPassword: (id: string) => `/api/v1/admin/users/${id}/reset-password`,
  },
  systemPrompts: {
    get: "/api/v1/system/prompts",
    update: "/api/v1/system/prompts",
  },
  observability: {
    traces: "/api/v1/observability/traces",
    evaluations: "/api/v1/observability/evaluations",
    tokenUsage: "/api/v1/observability/token-usage",
    diagnosticRules: "/api/v1/observability/diagnostic-rules",
    resetDiagnosticRules: "/api/v1/observability/diagnostic-rules/reset",
    logRetention: "/api/v1/observability/log-retention",
    executeLogCleanup: "/api/v1/observability/log-retention/execute",
  },
  rateLimits: {
    byTenant: (tenantId: string) => `/api/v1/admin/rate-limits/${tenantId}`,
  },
  errorEvents: {
    report: "/api/v1/error-events",
    list: "/api/v1/admin/error-events",
    detail: (id: string) => `/api/v1/admin/error-events/${id}`,
    resolve: (id: string) => `/api/v1/admin/error-events/${id}/resolve`,
  },
  notificationChannels: {
    list: "/api/v1/admin/notification-channels",
    create: "/api/v1/admin/notification-channels",
    update: (id: string) => `/api/v1/admin/notification-channels/${id}`,
    delete: (id: string) => `/api/v1/admin/notification-channels/${id}`,
    test: (id: string) => `/api/v1/admin/notification-channels/${id}/test`,
  },
} as const;
