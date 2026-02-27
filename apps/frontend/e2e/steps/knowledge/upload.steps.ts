import { expect } from "@playwright/test";
import { Given, Then } from "../fixtures";

Given(
  "使用者在知識庫 {string} 的詳情頁面",
  async ({ knowledgePage, page }, kbName: string) => {
    await knowledgePage.goto();
    await knowledgePage.clickKnowledgeBase(kbName);
    await expect(
      page.getByRole("heading", { name: "文件管理" }),
    ).toBeVisible({ timeout: 10000 });
  },
);

Then("應顯示文件上傳區域", async ({ knowledgeDetailPage }) => {
  await expect(knowledgeDetailPage.uploadDropzone).toBeVisible({
    timeout: 10000,
  });
});

Then("應顯示文件列表或空狀態", async ({ page }) => {
  const table = page.locator("table");
  const emptyState = page.getByText("尚未上傳任何文件。");
  await expect(table.or(emptyState)).toBeVisible({ timeout: 10000 });
});
