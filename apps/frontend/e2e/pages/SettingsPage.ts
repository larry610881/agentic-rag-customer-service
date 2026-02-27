import { type Page, type Locator } from "@playwright/test";

export class SettingsPage {
  readonly heading: Locator;
  readonly providerCards: Locator;
  readonly addProviderButton: Locator;
  readonly emptyState: Locator;
  readonly tabAll: Locator;
  readonly tabLLM: Locator;
  readonly tabEmbedding: Locator;

  constructor(private page: Page) {
    this.heading = page.getByRole("heading", { name: "供應商設定" });
    this.providerCards = page.locator("[data-slot='card']");
    this.addProviderButton = page.getByRole("button", { name: /新增供應商/ });
    this.emptyState = page.getByText("尚未設定供應商");
    this.tabAll = page.getByRole("button", { name: "全部" });
    this.tabLLM = page.getByRole("button", { name: "LLM" });
    this.tabEmbedding = page.getByRole("button", { name: "Embedding" });
  }

  async goto() {
    await this.page.goto("/settings/providers");
    await this.heading.waitFor({ timeout: 15000 });
  }

  async getProviderNames() {
    return this.providerCards
      .locator("[data-slot='card-title']")
      .allTextContents();
  }
}
