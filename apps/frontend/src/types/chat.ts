export interface Source {
  document_name: string;
  content_snippet: string;
  score: number;
}

export interface ToolCallInfo {
  tool_name: string;
  reasoning: string;
}

export interface ChatRequest {
  message: string;
  conversation_id?: string;
  knowledge_base_id?: string;
}

export interface ChatResponse {
  answer: string;
  conversation_id: string;
  tool_calls: ToolCallInfo[];
  sources: Source[];
}

export type MessageRole = "user" | "assistant";

export interface ChatMessage {
  id: string;
  role: MessageRole;
  content: string;
  sources?: Source[];
  tool_calls?: ToolCallInfo[];
  timestamp: string;
}
