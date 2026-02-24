export interface ConversationSummary {
  id: string;
  tenant_id: string;
  created_at: string;
}

export interface MessageDetail {
  id: string;
  role: string;
  content: string;
  created_at: string;
}

export interface ConversationDetail {
  id: string;
  tenant_id: string;
  messages: MessageDetail[];
  created_at: string;
}
