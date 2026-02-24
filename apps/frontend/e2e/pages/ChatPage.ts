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
    await this.page.goto("/chat");
    await this.messageInput.waitFor({ state: "visible", timeout: 30000 });
  }

  async sendMessage(text: string) {
    await this.messageInput.fill(text);
    // Wait for Send button to be enabled — signals KB auto-selection is complete
    const sendBtn = this.page.getByRole("button", { name: "Send", exact: true });
    await expect(sendBtn).toBeEnabled({ timeout: 15000 });
    await sendBtn.click();
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

  async sendMessageAndWait(text: string) {
    await this.sendMessage(text);
    await this.waitForAssistantResponse();
  }

  async expandThoughtPanel() {
    await this.thoughtPanel.last().click();
  }

  async getToolCallNames(): Promise<string[]> {
    // Expand the last Agent Actions panel
    const trigger = this.page.getByText(/Agent Actions/).last();
    if ((await trigger.count()) === 0) return [];
    await trigger.click();
    // Badge components use data-slot="badge" attribute
    const badges = this.page.locator('[data-slot="badge"]');
    return badges.allTextContents();
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
