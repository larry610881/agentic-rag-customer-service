import { expect } from "@playwright/test";
import { Given, When, Then } from "../fixtures";

Given("使用者在對話頁面", async ({ chatPage }) => {
  await chatPage.goto();
});

When("使用者輸入訊息 {string}", async ({ chatPage }, message: string) => {
  await chatPage.messageInput.fill(message);
});

When("使用者點擊送出按鈕", async ({ page, chatPage }) => {
  // Wait for Send button to be enabled (KB auto-selection must complete first)
  const sendBtn = page.getByRole("button", { name: "Send", exact: true });
  await expect(sendBtn).toBeEnabled({ timeout: 15000 });
  await sendBtn.click();
});

Then("應顯示 AI 回覆", async ({ chatPage }) => {
  await chatPage.waitForAssistantResponse();
});
