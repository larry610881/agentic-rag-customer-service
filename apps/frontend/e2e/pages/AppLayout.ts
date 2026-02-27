import { type Page, type Locator } from '@playwright/test';

export class AppLayout {
  readonly sidebar: Locator;
  readonly chatNavLink: Locator;
  readonly knowledgeNavLink: Locator;
  readonly tenantSelector: Locator;
  readonly logoutButton: Locator;

  constructor(private page: Page) {
    this.sidebar = page.locator('aside');
    this.chatNavLink = page.getByRole('link', { name: '對話' });
    this.knowledgeNavLink = page.getByRole('link', { name: '知識庫' });
    this.tenantSelector = page.getByLabel('選擇租戶');
    this.logoutButton = page.getByRole('button', { name: '登出' });
  }

  async navigateToChat() {
    await this.chatNavLink.click();
  }

  async navigateToKnowledge() {
    await this.knowledgeNavLink.click();
  }

  async selectTenant(name: string) {
    await this.tenantSelector.click();
    await this.page.getByRole('option', { name }).click();
  }

  async getCurrentTenant() {
    return this.tenantSelector.textContent();
  }
}
