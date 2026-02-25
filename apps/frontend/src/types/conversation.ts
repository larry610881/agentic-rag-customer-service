export interface ConversationSummary {
  id: string;
  tenant_id: string;
  bot_id: string | null;
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
  bot_id: string | null;
  messages: MessageDetail[];
  created_at: string;
}
