import { type Page, type Locator } from "@playwright/test";

export class BotPage {
  readonly heading: Locator;
  readonly botCards: Locator;
  readonly createBotButton: Locator;
  readonly emptyState: Locator;

  // Bot detail / form locators (Sprint W.4)
  readonly knowledgeModeSelect: Locator;
  readonly compileWikiCard: Locator;
  readonly compileWikiButton: Locator;
  readonly compileWikiConfirm: Locator;
  readonly wikiStatusBadge: Locator;

  constructor(private page: Page) {
    this.heading = page.getByRole("heading", { name: "機器人管理" });
    this.botCards = page.locator("[data-slot='card']");
    this.createBotButton = page.getByRole("button", { name: /建立/ });
    this.emptyState = page.getByText("尚無機器人");

    // Wiki / Knowledge mode locators (used in detail page)
    this.knowledgeModeSelect = page.getByLabel("知識模式");
    this.compileWikiCard = page.getByTestId("compile-wiki-card");
    this.compileWikiButton = page.getByTestId("compile-wiki-button");
    this.compileWikiConfirm = page.getByTestId("compile-wiki-confirm");
    this.wikiStatusBadge = page.getByTestId("wiki-status-badge");
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

  /**
   * Switch the bot's knowledge mode via the form selector.
   * Mode value: "rag" or "wiki".
   */
  async selectKnowledgeMode(mode: "rag" | "wiki") {
    const label =
      mode === "rag" ? "RAG（向量檢索，預設）" : "Wiki（知識圖譜）";
    await this.knowledgeModeSelect.click();
    await this.page.getByRole("option", { name: label }).click();
  }

  async clickCompileWiki() {
    await this.compileWikiButton.click();
  }

  async confirmCompileDialog() {
    await this.compileWikiConfirm.click();
  }
}
