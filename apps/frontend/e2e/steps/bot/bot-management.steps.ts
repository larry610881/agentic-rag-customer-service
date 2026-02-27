import { expect } from "@playwright/test";
import { When, Then } from "../fixtures";

When("使用者進入機器人管理頁面", async ({ botPage }) => {
  await botPage.goto();
});

Then("應顯示機器人管理標題", async ({ botPage }) => {
  await expect(botPage.heading).toBeVisible();
});

Then("應顯示機器人列表或空白狀態", async ({ page }) => {
  // Either bot cards or empty state message
  const content = page.locator(
    "[data-slot='card'], :text('尚無機器人')",
  );
  await expect(content.first()).toBeVisible({ timeout: 10000 });
});

Then("每個機器人應顯示名稱與狀態標籤", async ({ page }) => {
  // If bots exist, verify cards have title and badge
  const cards = page.locator("[data-slot='card']");
  const count = await cards.count();
  if (count > 0) {
    const firstCard = cards.first();
    await expect(firstCard.locator("[data-slot='card-title']")).toBeVisible();
    await expect(firstCard.locator("[data-slot='badge']").first()).toBeVisible();
  } else {
    // Empty state is acceptable
    await expect(page.getByText("尚無機器人")).toBeVisible();
  }
});
