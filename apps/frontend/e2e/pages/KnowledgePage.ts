import { type Page, type Locator } from '@playwright/test';

export class KnowledgePage {
  readonly heading: Locator;
  readonly kbList: Locator;
  readonly kbCards: Locator;
  readonly createKbButton: Locator;
  readonly createDialog: Locator;
  readonly kbNameInput: Locator;
  readonly kbDescriptionInput: Locator;
  readonly createSubmitButton: Locator;

  constructor(private page: Page) {
    this.heading = page.getByRole('heading', { name: 'Knowledge Bases' });
    this.kbList = page.locator('.grid.gap-4');
    this.kbCards = page.locator('.grid.gap-4').getByRole('link');
    this.createKbButton = page.getByRole('button', { name: 'Create Knowledge Base' });
    this.createDialog = page.getByRole('dialog');
    this.kbNameInput = page.getByLabel('Name');
    this.kbDescriptionInput = page.getByLabel('Description');
    this.createSubmitButton = page.getByRole('button', { name: 'Create' });
  }

  async goto() {
    await this.page.goto('/knowledge');
  }

  async getKnowledgeBases() {
    return this.kbCards.allTextContents();
  }

  async clickKnowledgeBase(name: string) {
    await this.page.getByRole('link').filter({ hasText: name }).click();
  }

  async openCreateDialog() {
    await this.createKbButton.click();
  }
}
