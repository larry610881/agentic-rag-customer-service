import { expect } from "@playwright/test";
import { When, Then } from "../fixtures";
import path from "path";

When("使用者上傳文件 {string}", async ({ knowledgeDetailPage }, filename: string) => {
  const filePath = path.resolve(__dirname, "../../fixtures", filename);
  await knowledgeDetailPage.uploadFile(filePath);
});

Then("應顯示文件處理狀態", async ({ page }) => {
  // Look for any processing indicator (status column or toast)
  const processing = page.getByText(/Processing|處理中|Pending|pending/);
  const completed = page.getByText(/Completed|completed|已完成/);
  // Either processing state is visible or it already completed quickly
  await expect(processing.or(completed).first()).toBeVisible({ timeout: 30000 });
});

Then("文件處理完成後應出現在列表中", async ({ knowledgeDetailPage }) => {
  // Wait for the document to appear in the list with completed status
  await knowledgeDetailPage.waitForDocumentCompleted("test-product.txt", 60000);
});
