import { type Page, type Locator } from "@playwright/test";

export class FeedbackPage {
  readonly heading: Locator;
  readonly statCards: Locator;
  readonly trendChart: Locator;
  readonly browserLink: Locator;
  readonly costTable: Locator;

  constructor(private page: Page) {
    this.heading = page.getByRole("heading", { name: "回饋分析" });
    this.statCards = page.locator("[data-slot='card']");
    this.trendChart = page.getByText("滿意度趨勢");
    this.browserLink = page.getByRole("link", { name: "差評瀏覽器" });
    this.costTable = page.getByText("Token 成本統計");
  }

  async goto() {
    await this.page.goto("/feedback");
    await this.heading.waitFor({ timeout: 15000 });
  }

  async gotoBrowser() {
    await this.page.goto("/feedback/browser");
    await this.page
      .getByRole("heading", { name: "差評瀏覽器" })
      .waitFor({ timeout: 15000 });
  }
}
