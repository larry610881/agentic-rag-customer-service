export interface ConversationSummary {
  id: string;
  tenant_id: string;
  bot_id: string | null;
  created_at: string;
}

export interface MessageStructuredContent {
  contact?: import("./chat").ContactCard | null;
  sources?: import("./chat").Source[] | null;
  blocks?: unknown[] | null;
}

export interface MessageDetail {
  id: string;
  role: string;
  content: string;
  created_at: string;
  latency_ms?: number | null;
  retrieved_chunks?: Record<string, unknown>[] | null;
  structured_content?: MessageStructuredContent | null;
}

export interface ConversationDetail {
  id: string;
  tenant_id: string;
  bot_id: string | null;
  messages: MessageDetail[];
  created_at: string;
}
