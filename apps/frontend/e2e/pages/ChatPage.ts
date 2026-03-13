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
      ".justify-start .whitespace-pre-wrap",
    );
    this.thoughtPanel = page.getByText(/Agent Actions/);
  }

  get streamingIndicator() {
    return this.page.getByRole("button", { name: "傳送中..." });
  }

  async goto() {
    await this.page.goto("/chat");

    // Wait for BotSelector to finish loading (skeletons have no text in a11y tree)
    // before trying to find the bot button.
    const botHeading = this.page.getByText("選擇一個機器人開始對話");
    const noBots = this.page.getByText("目前沒有可用的機器人");
    const loadError = this.page.getByText("無法載入機器人");
    await this.messageInput
      .or(botHeading)
      .or(noBots)
      .or(loadError)
      .first()
      .waitFor({ state: "visible", timeout: 30000 });

    // If bot selection screen appears, click the first matching bot card
    const inputVisible = await this.messageInput
      .isVisible()
      .catch(() => false);
    if (!inputVisible) {
      const botButton = this.page
        .getByRole("button", { name: /E2E 測試機器人/ })
        .first();
      await botButton.waitFor({ state: "attached", timeout: 15000 });
      // dispatchEvent bypasses viewport/scroll checks when many bots overflow
      await botButton.dispatchEvent("click");
    }
    await this.messageInput.waitFor({ state: "visible", timeout: 15000 });
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
    // UI renders "參考來源" as the citation section header
    const sourceHeader = this.page.getByText("參考來源", { exact: true });
    const count = await sourceHeader.count();
    if (count === 0) return [];
    const sourceSection = sourceHeader.last().locator("..");
    const cards = sourceSection.locator("button");
    return cards.allTextContents();
  }
}
