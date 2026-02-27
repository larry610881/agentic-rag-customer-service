import { type Page, type Locator } from "@playwright/test";

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
    this.heading = page.getByRole("heading", { name: "知識庫管理" });
    this.kbList = page.locator(".grid").first();
    this.kbCards = page.getByRole("link");
    this.createKbButton = page.getByRole("button", {
      name: "建立知識庫",
    });
    this.createDialog = page.getByRole("dialog");
    this.kbNameInput = page.getByLabel("名稱");
    this.kbDescriptionInput = page.getByLabel("描述");
    this.createSubmitButton = page.getByRole("button", { name: "建立" });
  }

  async goto() {
    // Wait for KB API response during navigation so list renders before interaction
    const kbApiPromise = this.page.waitForResponse(
      (resp) =>
        resp.url().includes("/knowledge-bases") && resp.status() === 200,
      { timeout: 20000 },
    );
    await this.page.goto("/knowledge");
    await this.heading.waitFor({ timeout: 15000 });
    await kbApiPromise.catch(() => {
      /* tenantId might not be set yet */
    });
  }

  async getKnowledgeBases() {
    return this.kbCards.allTextContents();
  }

  async clickKnowledgeBase(name: string) {
    const card = this.page.getByText(name, { exact: false }).first();
    await card.waitFor({ state: "visible", timeout: 20000 });
    await card.click();
  }

  async openCreateDialog() {
    await this.createKbButton.click();
  }
}
