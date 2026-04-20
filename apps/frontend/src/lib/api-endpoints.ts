export const API_ENDPOINTS = {
  auth: {
    login: "/api/v1/auth/login",
    refresh: "/api/v1/auth/refresh",
  },
  tenants: {
    list: "/api/v1/tenants",
    create: "/api/v1/tenants",
    config: (id: string) => `/api/v1/tenants/${id}/config`,
  },
  knowledgeBases: {
    list: "/api/v1/knowledge-bases",
    create: "/api/v1/knowledge-bases",
    update: (id: string) => `/api/v1/knowledge-bases/${id}`,
    delete: (id: string) => `/api/v1/knowledge-bases/${id}`,
    classify: (id: string) => `/api/v1/knowledge-bases/${id}/classify`,
    categories: (id: string) => `/api/v1/knowledge-bases/${id}/categories`,
    updateCategory: (kbId: string, catId: string) =>
      `/api/v1/knowledge-bases/${kbId}/categories/${catId}`,
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
    previewUrl: (kbId: string, docId: string) =>
      `/api/v1/knowledge-bases/${kbId}/documents/${docId}/preview-url`,
    children: (kbId: string, docId: string) =>
      `/api/v1/knowledge-bases/${kbId}/documents/${docId}/children`,
    requestUpload: (kbId: string) =>
      `/api/v1/knowledge-bases/${kbId}/documents/request-upload`,
    confirmUpload: (kbId: string) =>
      `/api/v1/knowledge-bases/${kbId}/documents/confirm-upload`,
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
    workers: (botId: string) => `/api/v1/bots/${botId}/workers`,
    worker: (botId: string, workerId: string) =>
      `/api/v1/bots/${botId}/workers/${workerId}`,
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
  usage: {
    byBot: "/api/v1/usage/by-bot",
    daily: "/api/v1/usage/daily",
    monthly: "/api/v1/usage/monthly",
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
  adminTools: {
    list: "/api/v1/admin/tools",
    update: (name: string) => `/api/v1/admin/tools/${name}`,
  },
  builtInTools: {
    list: "/api/v1/agent/built-in-tools",
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
  adminBots: {
    list: "/api/v1/admin/bots",
  },
  adminKnowledgeBases: {
    list: "/api/v1/admin/knowledge-bases",
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
    agentTraces: "/api/v1/observability/agent-traces",
    agentTraceDetail: (traceId: string) =>
      `/api/v1/observability/agent-traces/${traceId}`,
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
  promptOptimizer: {
    datasets: { list: "/api/v1/prompt-optimizer/datasets", create: "/api/v1/prompt-optimizer/datasets" },
    dataset: (id: string) => `/api/v1/prompt-optimizer/datasets/${id}`,
    datasetCases: (id: string) => `/api/v1/prompt-optimizer/datasets/${id}/cases`,
    datasetCase: (datasetId: string, caseId: string) =>
      `/api/v1/prompt-optimizer/datasets/${datasetId}/cases/${caseId}`,
    runs: { list: "/api/v1/prompt-optimizer/runs", create: "/api/v1/prompt-optimizer/runs" },
    run: (id: string) => `/api/v1/prompt-optimizer/runs/${id}`,
    runStop: (id: string) => `/api/v1/prompt-optimizer/runs/${id}/stop`,
    runRollback: (id: string) => `/api/v1/prompt-optimizer/runs/${id}/rollback`,
    runReport: (id: string) => `/api/v1/prompt-optimizer/runs/${id}/report`,
    runDiff: (id: string, iteration: number) => `/api/v1/prompt-optimizer/runs/${id}/diff/${iteration}`,
    runProgress: (id: string) => `/api/v1/prompt-optimizer/runs/${id}/progress`,
    eval: "/api/v1/prompt-optimizer/eval",
    estimate: "/api/v1/prompt-optimizer/estimate",
    validate: "/api/v1/prompt-optimizer/validate",
    exchangeRate: "/api/v1/prompt-optimizer/exchange-rate",
  },
  // HARDCODE - 地端模型 A/B 測試，正式上線前移除
  ollama: {
    abPresets: "/api/v1/ollama/ab-presets",
    modelStatus: (model: string) =>
      `/api/v1/ollama/model-status?model=${encodeURIComponent(model)}`,
  },
} as const;
