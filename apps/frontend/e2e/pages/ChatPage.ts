import { type Page, type Locator, expect } from "@playwright/test";

export class ChatPage {
  readonly messageInput: Locator;
  readonly sendButton: Locator;
  readonly assistantMessages: Locator;
  readonly thoughtPanel: Locator;

  constructor(private page: Page) {
    this.messageInput = page.getByLabel("Message input");
    this.sendButton = page.getByRole("button", { name: /^Send$|^Sending/ });
    this.assistantMessages = page.locator(
      ".bg-muted.text-muted-foreground .whitespace-pre-wrap",
    );
    this.thoughtPanel = page.getByText(/Agent Actions/);
  }

  get streamingIndicator() {
    return this.page.getByRole("button", { name: "Sending..." });
  }

  async goto() {
    // Register response listener BEFORE navigation to catch the KB fetch
    const kbPromise = this.page.waitForResponse(
      (resp) =>
        resp.url().includes("/knowledge-bases") && resp.status() === 200,
      { timeout: 15000 },
    );
    await this.page.goto("/chat");
    await this.messageInput.waitFor({ state: "visible", timeout: 15000 });
    // Wait for KB list to load so auto-KB-selection completes
    await kbPromise.catch(() => {
      /* KB fetch may not happen if tenantId is missing */
    });
  }

  async sendMessage(text: string) {
    await this.messageInput.fill(text);
    await this.sendButton.click();
  }

  async waitForAssistantResponse() {
    // Wait for assistant message to have actual content (streaming complete)
    await expect(this.assistantMessages.last()).toHaveText(/.+/, {
      timeout: 60000,
    });
    // Wait for send button to be re-enabled (streaming finished)
    await expect(
      this.page.getByRole("button", { name: "Send", exact: true }),
    ).toBeVisible({ timeout: 10000 });
  }

  async getLastAssistantMessage() {
    return this.assistantMessages.last().textContent();
  }

  async expandThoughtPanel() {
    await this.thoughtPanel.last().click();
  }

  async getCitations() {
    const sourceHeader = this.page.getByText("Sources", { exact: true });
    const count = await sourceHeader.count();
    if (count === 0) return [];
    const sourceSection = sourceHeader.last().locator("..");
    const cards = sourceSection.locator(".rounded-md.border");
    return cards.allTextContents();
  }
}
