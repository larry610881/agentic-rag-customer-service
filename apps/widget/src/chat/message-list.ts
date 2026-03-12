/**
 * Message list renderer — manages DOM elements for chat messages.
 */
export class MessageList {
  private container: HTMLElement;

  constructor(container: HTMLElement) {
    this.container = container;
  }

  /** Add a message bubble and return the element for streaming updates. */
  addMessage(role: "user" | "bot", text: string): HTMLElement {
    const bubble = document.createElement("div");
    bubble.className = `aw-bubble aw-bubble--${role}`;
    bubble.textContent = text;
    this.container.appendChild(bubble);
    this.scrollToBottom();
    return bubble;
  }

  /** Update an existing bubble's text (for streaming). */
  updateBubble(bubble: HTMLElement, text: string): void {
    bubble.textContent = text;
    this.scrollToBottom();
  }

  /** Scroll the message container to the bottom. */
  scrollToBottom(): void {
    this.container.scrollTop = this.container.scrollHeight;
  }
}
