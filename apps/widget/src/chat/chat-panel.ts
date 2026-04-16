import type { Source, WidgetConfig } from "../types";
import { cls } from "../constants";
import { MessageList } from "./message-list";
import { streamChat } from "./sse-client";
import { getStatusHint, getToolLabel } from "./tool-labels";

/**
 * Creates and manages the chat panel DOM and behavior.
 */
export class ChatPanel {
  readonly element: HTMLElement;
  readonly messageList: MessageList;

  private input: HTMLInputElement;
  private sendBtn: HTMLButtonElement;
  private chatUrl: string;
  private keepHistory: boolean;
  private showSources: boolean;
  private conversationId: string | null = null;
  private lsKey: string;
  private activeController: AbortController | null = null;
  private shortCode: string;
  private apiBase: string;

  constructor(
    config: WidgetConfig,
    apiBase: string,
    shortCode: string,
    onClose: () => void,
  ) {
    this.chatUrl = `${apiBase}/api/v1/widget/${shortCode}/chat/stream`;
    this.keepHistory = config.keep_history;
    this.showSources = config.show_sources;
    this.lsKey = `widget_conv_${shortCode}`;
    this.shortCode = shortCode;
    this.apiBase = apiBase;

    // Restore conversation_id
    if (this.keepHistory) {
      try {
        this.conversationId = localStorage.getItem(this.lsKey);
      } catch {
        // localStorage unavailable
      }
    }

    // Build DOM
    this.element = document.createElement("div");
    this.element.className = cls("panel");

    // Header
    const header = document.createElement("div");
    header.className = cls("header");

    const nameSpan = document.createElement("span");
    nameSpan.className = cls("header__name");
    nameSpan.textContent = config.name || "Chat";

    const closeBtn = document.createElement("button");
    closeBtn.className = cls("header__close");
    closeBtn.setAttribute("aria-label", "Close chat");
    closeBtn.innerHTML = "&times;";
    closeBtn.addEventListener("click", onClose);

    header.appendChild(nameSpan);
    header.appendChild(closeBtn);
    this.element.appendChild(header);

    // Messages
    const messagesEl = document.createElement("div");
    messagesEl.className = cls("messages");
    this.element.appendChild(messagesEl);
    this.messageList = new MessageList(messagesEl);

    // Input area
    const inputArea = document.createElement("div");
    inputArea.className = cls("input-area");

    this.input = document.createElement("input");
    this.input.type = "text";
    this.input.className = cls("input");
    this.input.placeholder =
      config.placeholder_text || "輸入訊息...";
    this.input.addEventListener("keydown", (e) => {
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        this.sendMessage();
      }
    });

    this.sendBtn = document.createElement("button");
    this.sendBtn.className = cls("send-btn");
    this.sendBtn.textContent = "送出";
    this.sendBtn.addEventListener("click", () => this.sendMessage());

    inputArea.appendChild(this.input);
    inputArea.appendChild(this.sendBtn);
    this.element.appendChild(inputArea);

    // Welcome message
    if (config.welcome_message) {
      this.messageList.addMessage("bot", config.welcome_message);
    }
  }

  focus(): void {
    this.input.focus();
  }

  /** Returns the messages container element. */
  getMessagesContainer(): HTMLElement {
    return this.element.querySelector(`.${cls("messages")}`) as HTMLElement;
  }

  private sendMessage(): void {
    const text = this.input.value.trim();
    if (!text) return;

    // --- TEST TRIGGER: remove before production ---
    if (text === "test") {
      this.input.value = "";
      this.messageList.addMessage("bot", "[Test] Widget 模擬錯誤已送出");
      fetch(`${this.apiBase}/api/v1/widget/${this.shortCode}/error`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          error_type: "NetworkError",
          message: "Failed to fetch: SSE connection aborted after 30s timeout",
          stack_trace: [
            "NetworkError: Failed to fetch",
            "    at ChatPanel.sendMessage (chat-panel.ts:135:22)",
            "    at HTMLButtonElement.onclick (widget.ts:89:14)",
            "    at EventTarget.dispatchEvent (<anonymous>)",
          ].join("\n"),
          path: window.location.pathname,
          user_agent: navigator.userAgent,
        }),
      }).catch(() => {});
      return;
    }
    // --- END TEST TRIGGER ---

    this.input.value = "";
    this.messageList.addMessage("user", text);

    const botBubble = this.messageList.addMessage("bot", "");
    this.messageList.showStatusHint(botBubble, getStatusHint("react_thinking"));
    let fullText = "";
    let pendingSources: Source[] = [];
    let messageId: string | null = null;
    let hasReceivedTokens = false;

    this.setSending(true);

    this.activeController = streamChat(
      this.chatUrl,
      {
        message: text,
        conversation_id:
          this.keepHistory ? this.conversationId : undefined,
      },
      (event) => {
        switch (event.type) {
          case "token":
            if (!hasReceivedTokens) {
              hasReceivedTokens = true;
            }
            fullText += event.content;
            this.messageList.updateBubble(botBubble, fullText);
            break;
          case "status": {
            const hint = getStatusHint(event.status);
            if (hint) {
              this.messageList.showStatusHint(botBubble, hint);
            }
            break;
          }
          case "tool_calls": {
            // Multi-step reasoning: show tool hint, clear previous text
            const toolName = event.tool_calls[0]?.tool_name || "";
            const label = getToolLabel(toolName);
            fullText = "";
            this.messageList.showStatusHint(
              botBubble,
              `\u{1f50d} ${label} 使用中...`,
            );
            break;
          }
          case "sources":
            pendingSources = event.sources;
            break;
          case "message_id":
            messageId = event.message_id;
            break;
          case "conversation_id":
            this.conversationId = event.conversation_id;
            if (this.keepHistory) {
              try {
                localStorage.setItem(this.lsKey, this.conversationId);
              } catch {
                // localStorage unavailable
              }
            }
            break;
          case "done":
            // Render sources block（文字引用）- 先做，讓 gallery 夾在 bubble 與 sources 之間
            if (this.showSources && pendingSources.length) {
              this.messageList.addSourcesBlock(botBubble, pendingSources, this.apiBase, this.shortCode);
            }
            // Render image gallery (for query_dm_with_image 等有 image_url 的 sources)
            if (pendingSources.length) {
              this.messageList.addImageGallery(botBubble, pendingSources);
            }
            // Render feedback buttons
            if (messageId && this.conversationId) {
              this.messageList.addFeedbackButtons(
                botBubble,
                messageId,
                this.conversationId,
                this.shortCode,
                this.apiBase,
              );
            }
            this.setSending(false);
            break;
          case "error":
            this.messageList.updateBubble(
              botBubble,
              event.message || "發生錯誤",
            );
            this.setSending(false);
            break;
        }
      },
      (err) => {
        // Report connection error
        fetch(`${this.apiBase}/api/v1/widget/${this.shortCode}/error`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            error_type: "ChatConnectionError",
            message: err.message,
            path: window.location.pathname,
            user_agent: navigator.userAgent,
          }),
        }).catch(() => {});
        this.messageList.updateBubble(botBubble, "連線失敗，請稍後再試");
        this.setSending(false);
      },
    );
  }

  private setSending(sending: boolean): void {
    this.sendBtn.disabled = sending;
    this.input.disabled = sending;
    if (!sending) {
      this.activeController = null;
    }
  }
}
