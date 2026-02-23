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
    upload: "/api/v1/documents/upload",
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
} as const;
