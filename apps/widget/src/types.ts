/** Widget config returned by GET /api/v1/widget/{short_code}/config */
export interface WidgetConfig {
  name: string;
  description: string;
  keep_history: boolean;
  show_sources: boolean;
  welcome_message: string;
  placeholder_text: string;
  greeting_messages: string[];
  greeting_animation: "fade" | "slide" | "typewriter";
  fab_icon_url?: string;
}

/** Source reference from RAG retrieval */
export interface Source {
  document_name: string;
  content_snippet: string;
  score: number;
  document_id?: string;
  /** DM 子頁頁碼（僅 query_dm_with_image tool 回傳） */
  page_number?: number;
  /** DM 子頁 PNG 圖片（signed URL） */
  image_url?: string;
}

/** Tool call info from agent */
export interface ToolCallInfo {
  tool_name: string;
  reasoning?: string;
}

/** SSE event types from POST /api/v1/widget/{short_code}/chat/stream */
export type SSEEvent =
  | { type: "token"; content: string }
  | { type: "conversation_id"; conversation_id: string }
  | { type: "message_id"; message_id: string }
  | { type: "status"; status: string }
  | { type: "sources"; sources: Source[] }
  | { type: "tool_calls"; tool_calls: ToolCallInfo[] }
  | { type: "done" }
  | { type: "error"; message: string };

/** Chat message for rendering */
export interface ChatMessage {
  role: "user" | "bot";
  content: string;
  /** Reference to the DOM bubble element for streaming updates */
  element?: HTMLElement;
}

