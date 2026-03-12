import type { AvatarRenderer, WidgetConfig } from "./types";
import { ChatPanel } from "./chat/chat-panel";
import { loadAvatar } from "./avatar/avatar-manager";
import styles from "./styles/widget.css?inline";

/**
 * Main widget controller.
 * Manages the FAB, chat panel, and optional avatar renderer.
 */
export class Widget {
  private root: HTMLElement;
  private fab: HTMLButtonElement;
  private chatPanel: ChatPanel;
  private avatar: AvatarRenderer | null = null;
  private isOpen = false;

  constructor(
    private config: WidgetConfig,
    private apiBase: string,
    private shortCode: string,
  ) {
    // Inject styles
    const style = document.createElement("style");
    style.textContent = styles;
    document.head.appendChild(style);

    // Root container
    this.root = document.createElement("div");
    this.root.id = "agentic-widget-root";
    document.body.appendChild(this.root);

    // FAB
    this.fab = document.createElement("button");
    this.fab.className = "aw-fab";
    this.fab.setAttribute("aria-label", "Open chat");
    this.fab.innerHTML =
      '<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>';
    this.fab.addEventListener("click", () => this.toggle());
    this.root.appendChild(this.fab);

    // Chat panel
    this.chatPanel = new ChatPanel(config, apiBase, shortCode, () =>
      this.toggle(),
    );
    this.root.appendChild(this.chatPanel.element);

    // Load avatar if needed
    this.initAvatar();
  }

  private async initAvatar(): Promise<void> {
    this.avatar = await loadAvatar(this.config, this.apiBase);
    if (!this.avatar) return;

    // Create avatar container and insert before messages
    const avatarArea = document.createElement("div");
    avatarArea.className = "aw-avatar";
    avatarArea.style.height = "180px";

    const messagesEl = this.chatPanel.getMessagesContainer();
    this.chatPanel.element.insertBefore(avatarArea, messagesEl);

    await this.avatar.mount(avatarArea);
  }

  private toggle(): void {
    this.isOpen = !this.isOpen;

    if (this.isOpen) {
      this.chatPanel.element.classList.add("aw-panel--open");
      this.fab.classList.add("aw-fab--hidden");
      this.chatPanel.focus();
    } else {
      this.chatPanel.element.classList.remove("aw-panel--open");
      this.fab.classList.remove("aw-fab--hidden");
    }
  }
}
