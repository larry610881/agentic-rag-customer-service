import { expect } from "@playwright/test";
import { Then } from "../fixtures";

Then("應顯示訊息輸入框", async ({ chatPage }) => {
  await chatPage.goto();
  await expect(chatPage.messageInput).toBeVisible({ timeout: 10000 });
});
