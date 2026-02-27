import { expect } from "@playwright/test";
import { Then } from "../fixtures";

Then("應顯示上傳區域", async ({ page }) => {
  // UploadDropzone renders a file input area
  const dropzone = page.locator(
    "input[type='file'], :text('拖曳檔案'), :text('上傳'), :text('Upload')",
  );
  await expect(dropzone.first()).toBeVisible({ timeout: 10000 });
});
