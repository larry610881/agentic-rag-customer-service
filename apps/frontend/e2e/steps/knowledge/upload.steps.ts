import { expect } from "@playwright/test";
import { Given, When, Then } from "../fixtures";
import path from "path";

Given(
  "使用者在知識庫 {string} 的詳情頁面",
  async ({ knowledgePage, page }, kbName: string) => {
    await knowledgePage.goto();
    await knowledgePage.clickKnowledgeBase(kbName);
    await expect(page.getByRole("heading", { name: kbName })).toBeVisible();
  },
);

When("使用者點擊上傳文件按鈕", async ({ knowledgeDetailPage }) => {
  await knowledgeDetailPage.chooseFileButton.click();
});

When(
  "使用者選擇檔案 {string}",
  async ({ knowledgeDetailPage }, fileName: string) => {
    const filePath = path.resolve(__dirname, "../../fixtures", fileName);
    await knowledgeDetailPage.uploadFile(filePath);
  },
);

When("使用者確認上傳", async ({ page }) => {
  const uploadButton = page.getByRole("button", { name: /upload|上傳/i });
  await uploadButton.click();
});

Then("應顯示上傳進度", async ({ knowledgeDetailPage }) => {
  await expect(knowledgeDetailPage.processingStatus).toBeVisible({
    timeout: 10000,
  });
});

Then(
  '文件狀態應從 "處理中" 變為 "已完成"',
  async ({ knowledgeDetailPage }) => {
    await knowledgeDetailPage.waitForProcessing();
  },
);

Then(
  "文件列表應包含 {string}",
  async ({ page }, fileName: string) => {
    await expect(page.getByText(fileName)).toBeVisible();
  },
);
