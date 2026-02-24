import { expect } from "@playwright/test";
import { When, Then } from "../fixtures";
import path from "path";

When("使用者上傳文件 {string}", async ({ knowledgeDetailPage }, filename: string) => {
  const filePath = path.resolve(__dirname, "../../fixtures", filename);
  await knowledgeDetailPage.uploadFile(filePath);
});

Then("應顯示文件處理進度", async ({ page }) => {
  // After successful upload, UploadProgress component shows "Processing document" with task status badge
  await expect(page.getByText("Processing document")).toBeVisible({ timeout: 30000 });
});
