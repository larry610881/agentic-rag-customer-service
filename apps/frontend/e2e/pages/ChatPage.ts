import { type Page, type Locator, expect } from "@playwright/test";

export class ChatPage {
  readonly messageInput: Locator;
  readonly sendButton: Locator;
  readonly assistantMessages: Locator;
  readonly thoughtPanel: Locator;

  constructor(private page: Page) {
    this.messageInput = page.getByLabel("訊息輸入");
    this.sendButton = page.getByRole("button", { name: /^傳送$|^傳送中/ });
    this.assistantMessages = page.locator(
      ".bg-muted.text-muted-foreground .whitespace-pre-wrap",
    );
    this.thoughtPanel = page.getByText(/Agent Actions/);
  }

  get streamingIndicator() {
    return this.page.getByRole("button", { name: "傳送中..." });
  }

  async goto() {
    await this.page.goto("/chat");
    // If bot selection screen appears, click the first bot card
    const botCard = this.page.getByText("E2E 測試機器人").first();
    const inputVisible = await this.messageInput
      .isVisible()
      .catch(() => false);
    if (!inputVisible) {
      try {
        await botCard.waitFor({ state: "visible", timeout: 10000 });
        await botCard.click();
      } catch {
        // Bot card not found, message input may already be visible
      }
    }
    await this.messageInput.waitFor({ state: "visible", timeout: 30000 });
  }

  async sendMessage(text: string) {
    await this.messageInput.fill(text);
    // Wait for Send button to be enabled — signals KB auto-selection is complete
    const sendBtn = this.page.getByRole("button", {
      name: "傳送",
      exact: true,
    });
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
      this.page.getByRole("button", { name: "傳送", exact: true }),
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
