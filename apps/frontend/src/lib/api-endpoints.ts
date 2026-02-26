export const API_ENDPOINTS = {
  auth: {
    login: "/api/v1/auth/login",
  },
  tenants: {
    list: "/api/v1/tenants",
    create: "/api/v1/tenants",
  },
  knowledgeBases: {
    list: "/api/v1/knowledge-bases",
    create: "/api/v1/knowledge-bases",
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
  },
} as const;
