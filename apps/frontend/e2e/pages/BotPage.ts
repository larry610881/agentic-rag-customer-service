import { type Page, type Locator } from "@playwright/test";

export class BotPage {
  readonly heading: Locator;
  readonly botCards: Locator;
  readonly createBotButton: Locator;
  readonly emptyState: Locator;

  constructor(private page: Page) {
    this.heading = page.getByRole("heading", { name: "機器人管理" });
    this.botCards = page.locator("[data-slot='card']");
    this.createBotButton = page.getByRole("button", { name: /建立/ });
    this.emptyState = page.getByText("尚無機器人");
  }

  async goto() {
    await this.page.goto("/bots");
    await this.heading.waitFor({ timeout: 15000 });
  }

  async getBotNames() {
    return this.botCards.locator("[data-slot='card-title']").allTextContents();
  }

  async clickBot(name: string) {
    const card = this.page.getByText(name, { exact: false }).first();
    await card.waitFor({ state: "visible", timeout: 10000 });
    await card.click();
  }
}
