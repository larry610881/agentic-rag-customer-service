import { expect } from "@playwright/test";
import { When, Then } from "../fixtures";
import path from "path";
import { fileURLToPath } from "url";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

When("使用者上傳文件 {string}", async ({ knowledgeDetailPage }, filename: string) => {
  const filePath = path.resolve(__dirname, "../../fixtures", filename);
  await knowledgeDetailPage.uploadFile(filePath);
});

Then("應顯示文件處理進度", async ({ page }) => {
  // After upload, the document appears in the file list table.
  // In E2E mode (no real embedding service), status may be "處理中" or "失敗".
  // Use .first() since stale rows from previous runs may exist.
  const fileRow = page.getByRole("row", { name: /test-product\.txt/ }).first();
  await expect(fileRow).toBeVisible({ timeout: 30000 });
});
