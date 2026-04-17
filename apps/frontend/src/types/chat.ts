export interface Source {
  document_name: string;
  content_snippet: string;
  score: number;
  chunk_id?: string;
  document_id?: string;
  /** DM 子頁頁碼（僅 query_dm_with_image tool 回傳） */
  page_number?: number;
  /** DM 子頁 PNG 圖片（signed URL，僅 query_dm_with_image tool 回傳） */
  image_url?: string;
}

export interface ToolCallInfo {
  tool_name: string;
  /** Backend resolve 後的中文顯示名稱；缺省時前端 fallback 為 tool_name */
  label?: string;
  reasoning: string;
  iteration?: number;
}

/** 由 transfer_to_human_agent tool 產生的聯絡按鈕資料 */
export interface ContactCard {
  label: string;
  url: string;
  type: "url" | "phone";
}

export interface ChatRequest {
  message: string;
  conversation_id?: string;
  knowledge_base_id?: string;
  bot_id?: string;
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
  /** 由 transfer_to_human_agent tool 產生的聯絡按鈕（可選） */
  contact?: ContactCard;
  timestamp: string;
  feedbackRating?: "thumbs_up" | "thumbs_down";
}
