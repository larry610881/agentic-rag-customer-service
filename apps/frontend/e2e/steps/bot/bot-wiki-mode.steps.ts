import { expect } from "@playwright/test";
import { Given, When, Then } from "../fixtures";

let wikiCompileCalled = false;

Given("Wiki 編譯與狀態端點已被 mock", async ({ page }) => {
  wikiCompileCalled = false;

  // Mock GET /api/v1/bots/:botId/wiki/status — return ready with stats
  await page.route(/\/api\/v1\/bots\/[^/]+\/wiki\/status$/, async (route) => {
    if (route.request().method() === "GET") {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          wiki_graph_id: "g-mock-1",
          bot_id: "mock-bot",
          kb_id: "mock-kb",
          status: "ready",
          node_count: 42,
          edge_count: 87,
          cluster_count: 5,
          doc_count: 10,
          compiled_at: "2026-04-10T10:00:00Z",
          token_usage: {
            input: 5000,
            output: 1200,
            total: 6200,
            estimated_cost: 0.0125,
          },
          errors: null,
        }),
      });
      return;
    }
    await route.continue();
  });

  // Mock POST /api/v1/bots/:botId/wiki/compile — return 202
  await page.route(/\/api\/v1\/bots\/[^/]+\/wiki\/compile$/, async (route) => {
    if (route.request().method() === "POST") {
      wikiCompileCalled = true;
      await route.fulfill({
        status: 202,
        contentType: "application/json",
        body: JSON.stringify({
          bot_id: "mock-bot",
          status: "accepted",
          message: "Wiki compilation started",
        }),
      });
      return;
    }
    await route.continue();
  });
});

When("使用者點擊第一個機器人卡片", async ({ botPage, page }) => {
  await botPage.botCards.first().waitFor({ state: "visible", timeout: 10000 });
  await botPage.botCards.first().click();
  // Wait for navigation to the bot detail page
  await page.waitForURL(/\/bots\/.+/, { timeout: 10000 });
});

When(
  "使用者切換知識模式為 {string}",
  async ({ botPage }, mode: string) => {
    if (mode !== "rag" && mode !== "wiki") {
      throw new Error(`Unknown knowledge mode: ${mode}`);
    }
    await botPage.selectKnowledgeMode(mode);
  },
);

Then("應顯示 Wiki 編譯卡片", async ({ botPage }) => {
  await expect(botPage.compileWikiCard).toBeVisible({ timeout: 10000 });
});

Then(
  "應顯示導航策略 {string}",
  async ({ page }, strategyLabel: string) => {
    // The label appears in the Select trigger
    await expect(page.getByText(strategyLabel).first()).toBeVisible();
  },
);

When("使用者點擊「編譯 Wiki」按鈕", async ({ botPage }) => {
  await botPage.clickCompileWiki();
});

Then("應顯示確認編譯對話框", async ({ page }) => {
  await expect(page.getByText("確認編譯 Wiki？")).toBeVisible();
});

When("使用者確認編譯", async ({ botPage }) => {
  await botPage.confirmCompileDialog();
});

Then("Wiki 編譯端點應被呼叫", async () => {
  // Allow the network request to complete
  await new Promise((resolve) => setTimeout(resolve, 500));
  expect(wikiCompileCalled).toBe(true);
});

Then(
  "Wiki 狀態 badge 應顯示 {string}",
  async ({ botPage }, label: string) => {
    await expect(botPage.wikiStatusBadge).toBeVisible({ timeout: 10000 });
    await expect(botPage.wikiStatusBadge).toContainText(label);
  },
);

Then("應顯示節點統計與 Token 用量", async ({ page }) => {
  await expect(page.getByText("42").first()).toBeVisible();
  await expect(page.getByText("87").first()).toBeVisible();
  await expect(page.getByText(/Token 使用/)).toBeVisible();
});
