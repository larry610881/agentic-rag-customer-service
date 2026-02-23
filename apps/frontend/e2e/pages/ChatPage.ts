import { type Page, type Locator, expect } from '@playwright/test';

export class ChatPage {
  readonly messageInput: Locator;
  readonly sendButton: Locator;
  readonly messageList: Locator;
  readonly assistantMessages: Locator;
  readonly citationCards: Locator;
  readonly thoughtPanel: Locator;
  readonly streamingIndicator: Locator;

  constructor(private page: Page) {
    this.messageInput = page.getByLabel('Message input');
    this.sendButton = page.getByRole('button', { name: 'Send' });
    this.messageList = page.locator('.flex.flex-col.gap-4');
    this.assistantMessages = page.locator('.bg-muted.text-muted-foreground .whitespace-pre-wrap');
    this.citationCards = page.getByText('Sources').locator('..');
    this.thoughtPanel = page.getByText(/Agent Actions/);
    this.streamingIndicator = page.getByRole('button', { name: 'Sending...' });
  }

  async goto() {
    await this.page.goto('/chat');
  }

  async sendMessage(text: string) {
    await this.messageInput.fill(text);
    await this.sendButton.click();
  }

  async waitForAssistantResponse() {
    await expect(this.assistantMessages.last()).toBeVisible({ timeout: 30000 });
    await expect(this.streamingIndicator).toBeHidden({ timeout: 30000 });
  }

  async getLastAssistantMessage() {
    return this.assistantMessages.last().textContent();
  }

  async expandThoughtPanel() {
    await this.thoughtPanel.last().click();
  }

  async getCitations() {
    const sourceSections = this.page.locator('.flex.flex-col.gap-1.sm\\:ml-4');
    const count = await sourceSections.count();
    if (count === 0) return [];
    const lastSection = sourceSections.last();
    const cards = lastSection.locator('.rounded-md.border');
    return cards.allTextContents();
  }
}
