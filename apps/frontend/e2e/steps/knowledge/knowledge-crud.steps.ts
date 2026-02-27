import { expect } from "@playwright/test";
import { Given, When, Then } from "../fixtures";

Then("應顯示知識庫列表", async ({ knowledgePage }) => {
  await expect(knowledgePage.kbList).toBeVisible({ timeout: 10000 });
});

When(
  "使用者點擊知識庫 {string}",
  async ({ knowledgePage }, kbName: string) => {
    await knowledgePage.clickKnowledgeBase(kbName);
  },
);

Then("應顯示文件管理頁面", async ({ page }) => {
  await expect(
    page.getByRole("heading", { name: "文件管理" }),
  ).toBeVisible({ timeout: 10000 });
});

Then("應顯示文件列表", async ({ page }) => {
  // Accept either a document table or the empty-state message
  const tableOrEmpty = page.locator(
    'table, :text("尚未上傳任何文件。")',
  );
  await expect(tableOrEmpty.first()).toBeVisible({ timeout: 10000 });
});
