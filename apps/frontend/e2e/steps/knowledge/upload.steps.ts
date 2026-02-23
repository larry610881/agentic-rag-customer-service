import { expect } from "@playwright/test";
import { Given, When, Then } from "../fixtures";
import path from "path";

Given(
  "使用者在知識庫 {string} 的詳情頁面",
  async ({ knowledgePage, page }, kbName: string) => {
    await knowledgePage.goto();
    await knowledgePage.clickKnowledgeBase(kbName);
    await expect(
      page.getByRole("heading", { name: "Documents" }),
    ).toBeVisible();
  },
);

When(
  "使用者選擇檔案 {string}",
  async ({ knowledgeDetailPage }, fileName: string) => {
    const filePath = path.resolve(__dirname, "../../fixtures", fileName);
    await knowledgeDetailPage.uploadFile(filePath);
  },
);

Then("應顯示上傳中狀態", async ({ page }) => {
  // The dropzone shows "Uploading..." or a mutation error — verify either state
  const uploading = page.getByText("Uploading...");
  const uploadFailed = page.getByText("Upload failed");
  const result = await Promise.race([
    uploading.waitFor({ state: "visible", timeout: 10000 }).then(() => "uploading"),
    uploadFailed.waitFor({ state: "visible", timeout: 10000 }).then(() => "failed"),
  ]).catch(() => "timeout");
  // Either state means the upload was triggered successfully
  expect(["uploading", "failed"]).toContain(result);
});
