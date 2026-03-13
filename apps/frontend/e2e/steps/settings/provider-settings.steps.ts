import { expect } from "@playwright/test";
import { When, Then } from "../fixtures";

When("使用者進入供應商設定頁面", async ({ settingsPage }) => {
  await settingsPage.goto();
});

Then("應顯示供應商設定標題", async ({ settingsPage }) => {
  await expect(settingsPage.heading).toBeVisible();
});

Then("應顯示供應商列表或空白狀態", async ({ page }) => {
  const content = page.locator(
    "[data-slot='card'], :text('尚未設定供應商')",
  );
  await expect(content.first()).toBeVisible({ timeout: 10000 });
});

Then("應顯示新增供應商按鈕", async ({ page }) => {
  await expect(
    page.getByRole("button", { name: /新增供應商/ }),
  ).toBeVisible();
});

Then("應顯示 LLM 與 API Key 分頁按鈕", async ({ settingsPage }) => {
  await expect(settingsPage.tabLLM).toBeVisible();
  await expect(settingsPage.tabApiKey).toBeVisible();
});
