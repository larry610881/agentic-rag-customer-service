/** Widget config returned by GET /api/v1/widget/{short_code}/config */
export interface WidgetConfig {
  name: string;
  description: string;
  keep_history: boolean;
  avatar_type: "none" | "live2d" | "vrm";
  avatar_model_url: string;
  welcome_message: string;
  placeholder_text: string;
}

/** SSE event types from POST /api/v1/widget/{short_code}/chat/stream */
export type SSEEvent =
  | { type: "token"; content: string }
  | { type: "conversation_id"; conversation_id: string }
  | { type: "done" }
  | { type: "error"; message: string };

/** Chat message for rendering */
export interface ChatMessage {
  role: "user" | "bot";
  content: string;
  /** Reference to the DOM bubble element for streaming updates */
  element?: HTMLElement;
}

/** Avatar renderer interface */
export interface AvatarRenderer {
  mount(container: HTMLElement): Promise<void>;
  dispose(): void;
}
