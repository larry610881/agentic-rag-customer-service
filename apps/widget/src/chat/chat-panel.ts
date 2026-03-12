import type { WidgetConfig } from "../types";
import { MessageList } from "./message-list";
import { streamChat } from "./sse-client";

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
  private conversationId: string | null = null;
  private lsKey: string;
  private activeController: AbortController | null = null;

  constructor(
    config: WidgetConfig,
    apiBase: string,
    shortCode: string,
    onClose: () => void,
  ) {
    this.chatUrl = `${apiBase}/api/v1/widget/${shortCode}/chat/stream`;
    this.keepHistory = config.keep_history;
    this.lsKey = `widget_conv_${shortCode}`;

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
    this.element.className = "aw-panel";

    // Header
    const header = document.createElement("div");
    header.className = "aw-header";

    const nameSpan = document.createElement("span");
    nameSpan.className = "aw-header__name";
    nameSpan.textContent = config.name || "Chat";

    const closeBtn = document.createElement("button");
    closeBtn.className = "aw-header__close";
    closeBtn.setAttribute("aria-label", "Close chat");
    closeBtn.innerHTML = "&times;";
    closeBtn.addEventListener("click", onClose);

    header.appendChild(nameSpan);
    header.appendChild(closeBtn);
    this.element.appendChild(header);

    // Messages
    const messagesEl = document.createElement("div");
    messagesEl.className = "aw-messages";
    this.element.appendChild(messagesEl);
    this.messageList = new MessageList(messagesEl);

    // Input area
    const inputArea = document.createElement("div");
    inputArea.className = "aw-input-area";

    this.input = document.createElement("input");
    this.input.type = "text";
    this.input.className = "aw-input";
    this.input.placeholder =
      config.placeholder_text || "輸入訊息...";
    this.input.addEventListener("keydown", (e) => {
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        this.sendMessage();
      }
    });

    this.sendBtn = document.createElement("button");
    this.sendBtn.className = "aw-send-btn";
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

  /** Returns the messages container for inserting avatar area before it. */
  getMessagesContainer(): HTMLElement {
    return this.element.querySelector(".aw-messages") as HTMLElement;
  }

  private sendMessage(): void {
    const text = this.input.value.trim();
    if (!text) return;

    this.input.value = "";
    this.messageList.addMessage("user", text);

    const botBubble = this.messageList.addMessage("bot", "...");
    let fullText = "";

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
            fullText += event.content;
            this.messageList.updateBubble(botBubble, fullText);
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
      () => {
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
