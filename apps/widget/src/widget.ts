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
  private greetingEl: HTMLElement | null = null;
  private greetingTimer: ReturnType<typeof setTimeout> | null = null;
  private greetingIndex = 0;

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

    // Chat icon — filled bubble with typing dots
    const chatIcon = document.createElement("span");
    chatIcon.className = "aw-fab__icon-chat";
    chatIcon.innerHTML = `<svg width="28" height="28" viewBox="0 0 24 24" fill="currentColor">
      <path d="M20 2H4c-1.1 0-2 .9-2 2v18l4-4h14c1.1 0 2-.9 2-2V4c0-1.1-.9-2-2-2z"/>
      <circle cx="8" cy="10" r="1.2" fill="#fff"/>
      <circle cx="12" cy="10" r="1.2" fill="#fff"/>
      <circle cx="16" cy="10" r="1.2" fill="#fff"/>
    </svg>`;

    // Close icon — X
    const closeIcon = document.createElement("span");
    closeIcon.className = "aw-fab__icon-close";
    closeIcon.innerHTML = `<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round">
      <line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>
    </svg>`;

    this.fab.appendChild(chatIcon);
    this.fab.appendChild(closeIcon);

    // Avatar FAB variant — gradient background when avatar is enabled
    if (config.avatar_type && config.avatar_type !== "none") {
      this.fab.classList.add("aw-fab--avatar");
    }

    this.fab.addEventListener("click", () => this.toggle());
    this.root.appendChild(this.fab);

    // Chat panel
    this.chatPanel = new ChatPanel(config, apiBase, shortCode, () =>
      this.toggle(),
    );
    this.root.appendChild(this.chatPanel.element);

    // Load avatar if needed
    this.initAvatar();

    // Start greeting bubble (delayed)
    if (config.greeting_messages && config.greeting_messages.length > 0) {
      setTimeout(() => {
        if (!this.isOpen) {
          this.initGreetingBubble(config.greeting_messages, config.greeting_animation);
        }
      }, 2000);
    }
  }

  private async initAvatar(): Promise<void> {
    this.avatar = await loadAvatar(this.config, this.apiBase);
    if (!this.avatar) return;

    // Replace the round FAB with full-size avatar character
    this.fab.innerHTML = "";
    this.fab.classList.remove("aw-fab--avatar");
    this.fab.classList.add("aw-fab--avatar-live");

    // Mount avatar renderer into the FAB container
    const avatarContainer = document.createElement("div");
    avatarContainer.className = "aw-fab__avatar";
    this.fab.appendChild(avatarContainer);

    // Shift panel above the avatar character
    this.chatPanel.element.classList.add("aw-panel--above-avatar");

    await this.avatar.mount(avatarContainer);
  }

  private toggle(): void {
    this.isOpen = !this.isOpen;

    if (this.isOpen) {
      this.chatPanel.element.classList.add("aw-panel--open");
      this.fab.classList.add("aw-fab--open");
      this.fab.setAttribute("aria-label", "Close chat");
      this.chatPanel.focus();
      this.stopGreeting();
    } else {
      this.chatPanel.element.classList.remove("aw-panel--open");
      this.fab.classList.remove("aw-fab--open");
      this.fab.setAttribute("aria-label", "Open chat");
      this.restartGreeting();
    }
  }

  /* ── Greeting Bubble ──────────────────────────────────────── */

  private initGreetingBubble(
    messages: string[],
    animation: "fade" | "slide" | "typewriter",
  ): void {
    if (!messages.length) return;

    this.greetingEl = document.createElement("div");
    this.greetingEl.className = "aw-greeting";
    this.greetingEl.addEventListener("click", () => {
      if (!this.isOpen) this.toggle();
    });
    this.root.appendChild(this.greetingEl);

    this.greetingIndex = 0;
    this.showGreeting(messages[this.greetingIndex], animation);

    if (messages.length > 1) {
      this.scheduleNextGreeting(messages, animation);
    }
  }

  private scheduleNextGreeting(
    messages: string[],
    animation: "fade" | "slide" | "typewriter",
  ): void {
    const isLastMessage = this.greetingIndex === messages.length - 1;
    const baseDelay = animation === "typewriter"
      ? messages[this.greetingIndex].length * 50 + 3000
      : 5000;
    // After last message in the round, pause 10s before restarting
    const delay = isLastMessage ? baseDelay + 10000 : baseDelay;

    this.greetingTimer = setTimeout(() => {
      this.greetingIndex = (this.greetingIndex + 1) % messages.length;
      this.transitionGreeting(messages[this.greetingIndex], animation, () => {
        this.scheduleNextGreeting(messages, animation);
      });
    }, delay);
  }

  private showGreeting(
    text: string,
    animation: "fade" | "slide" | "typewriter",
  ): void {
    if (!this.greetingEl) return;

    if (animation === "typewriter") {
      this.greetingEl.textContent = "";
      this.greetingEl.classList.add("aw-greeting--visible");
      this.typeText(this.greetingEl, text, 0);
    } else {
      this.greetingEl.textContent = text;
      this.greetingEl.classList.add("aw-greeting--visible");
    }
  }

  private typeText(el: HTMLElement, text: string, idx: number): void {
    if (idx >= text.length || !this.greetingEl) return;
    el.textContent += text[idx];
    setTimeout(() => this.typeText(el, text, idx + 1), 50);
  }

  private transitionGreeting(
    text: string,
    animation: "fade" | "slide" | "typewriter",
    onDone: () => void,
  ): void {
    if (!this.greetingEl) return;

    if (animation === "fade") {
      this.greetingEl.classList.add("aw-greeting--fade-out");
      setTimeout(() => {
        if (!this.greetingEl) return;
        this.greetingEl.textContent = text;
        this.greetingEl.classList.remove("aw-greeting--fade-out");
        onDone();
      }, 300);
    } else if (animation === "slide") {
      this.greetingEl.classList.add("aw-greeting--slide-out");
      setTimeout(() => {
        if (!this.greetingEl) return;
        this.greetingEl.textContent = text;
        this.greetingEl.classList.remove("aw-greeting--slide-out");
        this.greetingEl.classList.add("aw-greeting--slide-in");
        setTimeout(() => {
          this.greetingEl?.classList.remove("aw-greeting--slide-in");
          onDone();
        }, 300);
      }, 300);
    } else {
      // typewriter
      this.greetingEl.textContent = "";
      this.typeText(this.greetingEl, text, 0);
      onDone();
    }
  }

  private stopGreeting(): void {
    if (this.greetingTimer) {
      clearTimeout(this.greetingTimer);
      this.greetingTimer = null;
    }
    if (this.greetingEl) {
      this.greetingEl.classList.remove("aw-greeting--visible");
    }
  }

  private restartGreeting(): void {
    const msgs = this.config.greeting_messages;
    const anim = this.config.greeting_animation;
    if (!msgs || !msgs.length || !this.greetingEl) return;

    this.greetingIndex = 0;
    setTimeout(() => {
      if (this.isOpen) return;
      this.showGreeting(msgs[this.greetingIndex], anim);
      if (msgs.length > 1) {
        this.scheduleNextGreeting(msgs, anim);
      }
    }, 2000);
  }
}
