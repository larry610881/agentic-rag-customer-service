import type { Source } from "../types";

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
    bubble.classList.remove("aw-status-hint");
    bubble.textContent = text;
    this.scrollToBottom();
  }

  /** Show a status hint inside the bot bubble (replaces text temporarily). */
  showStatusHint(bubble: HTMLElement, hint: string): void {
    bubble.textContent = hint;
    bubble.classList.add("aw-status-hint");
    this.scrollToBottom();
  }

  /** Add a sources block below the bot bubble. */
  addSourcesBlock(bubble: HTMLElement, sources: Source[]): void {
    if (!sources.length) return;

    const block = document.createElement("div");
    block.className = "aw-sources";

    const toggle = document.createElement("button");
    toggle.className = "aw-sources__toggle";
    toggle.textContent = `\u{1f4da} 參考來源（${sources.length}）`;
    toggle.addEventListener("click", () => {
      list.style.display = list.style.display === "none" ? "block" : "none";
      toggle.classList.toggle("aw-sources__toggle--open");
    });

    const list = document.createElement("div");
    list.className = "aw-sources__list";
    list.style.display = "none";

    for (const src of sources) {
      const item = document.createElement("div");
      item.className = "aw-sources__item";

      const name = document.createElement("div");
      name.className = "aw-sources__name";
      name.textContent = src.document_name;

      const snippet = document.createElement("div");
      snippet.className = "aw-sources__snippet";
      snippet.textContent = src.content_snippet;

      item.appendChild(name);
      item.appendChild(snippet);
      list.appendChild(item);
    }

    block.appendChild(toggle);
    block.appendChild(list);

    // Insert after the bubble
    bubble.parentElement?.insertBefore(block, bubble.nextSibling);
    this.scrollToBottom();
  }

  /** Add feedback (thumbs up/down) buttons below the bot bubble. */
  addFeedbackButtons(
    bubble: HTMLElement,
    messageId: string,
    conversationId: string,
    shortCode: string,
    apiBase: string,
  ): void {
    const container = document.createElement("div");
    container.className = "aw-feedback";

    const upBtn = document.createElement("button");
    upBtn.className = "aw-feedback__btn";
    upBtn.textContent = "\u{1f44d}";
    upBtn.title = "有幫助";

    const downBtn = document.createElement("button");
    downBtn.className = "aw-feedback__btn";
    downBtn.textContent = "\u{1f44e}";
    downBtn.title = "沒幫助";

    const submitFeedback = async (
      rating: string,
      comment?: string,
      tags?: string[],
    ) => {
      try {
        const body: Record<string, unknown> = {
          conversation_id: conversationId,
          message_id: messageId,
          rating,
        };
        if (comment) body.comment = comment;
        if (tags?.length) body.tags = tags;

        await fetch(
          `${apiBase}/api/v1/widget/${shortCode}/feedback`,
          {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(body),
          },
        );
      } catch (err) {
        console.warn("[widget] feedback submission failed:", err);
      }
    };

    upBtn.addEventListener("click", async () => {
      await submitFeedback("thumbs_up");
      container.innerHTML = "";
      const done = document.createElement("span");
      done.className = "aw-feedback__done";
      done.textContent = "感謝回饋！";
      container.appendChild(done);
    });

    downBtn.addEventListener("click", () => {
      upBtn.style.display = "none";
      downBtn.classList.add("aw-feedback__btn--active");
      downBtn.disabled = true;
      this._showFeedbackForm(container, submitFeedback);
    });

    container.appendChild(upBtn);
    container.appendChild(downBtn);

    // Insert after the bubble (and after sources block if present)
    let insertAfter: Element = bubble;
    const nextEl = bubble.nextElementSibling;
    if (nextEl?.classList.contains("aw-sources")) {
      insertAfter = nextEl;
    }
    insertAfter.parentElement?.insertBefore(
      container,
      insertAfter.nextSibling,
    );
    this.scrollToBottom();
  }

  /** Render the negative feedback form with tags + comment. */
  private _showFeedbackForm(
    container: HTMLElement,
    submitFn: (
      rating: string,
      comment?: string,
      tags?: string[],
    ) => Promise<void>,
  ): void {
    const form = document.createElement("div");
    form.className = "aw-feedback__form";

    const TAGS = ["答案不正確", "不完整", "沒回答問題", "語氣不好"];
    const selectedTags = new Set<string>();

    const tagsContainer = document.createElement("div");
    tagsContainer.className = "aw-feedback__tags";

    for (const tag of TAGS) {
      const tagBtn = document.createElement("button");
      tagBtn.className = "aw-feedback__tag";
      tagBtn.textContent = tag;
      tagBtn.addEventListener("click", () => {
        if (selectedTags.has(tag)) {
          selectedTags.delete(tag);
          tagBtn.classList.remove("aw-feedback__tag--selected");
        } else {
          selectedTags.add(tag);
          tagBtn.classList.add("aw-feedback__tag--selected");
        }
      });
      tagsContainer.appendChild(tagBtn);
    }

    const input = document.createElement("input");
    input.className = "aw-feedback__input";
    input.type = "text";
    input.placeholder = "其他回饋（選填）";

    const submitBtn = document.createElement("button");
    submitBtn.className = "aw-feedback__submit";
    submitBtn.textContent = "送出";
    submitBtn.addEventListener("click", async () => {
      const comment = input.value.trim() || undefined;
      const tags = [...selectedTags];
      await submitFn("thumbs_down", comment, tags);
      container.innerHTML = "";
      const done = document.createElement("span");
      done.className = "aw-feedback__done";
      done.textContent = "感謝回饋！";
      container.appendChild(done);
    });

    form.appendChild(tagsContainer);
    form.appendChild(input);
    form.appendChild(submitBtn);
    container.appendChild(form);
    this.scrollToBottom();
  }

  /** Scroll the message container to the bottom. */
  scrollToBottom(): void {
    this.container.scrollTop = this.container.scrollHeight;
  }
}
