import { Given, When, Then } from "../fixtures";

Given("使用者在對話頁面", async ({ chatPage }) => {
  await chatPage.goto();
});

When("使用者輸入訊息 {string}", async ({ chatPage }, message: string) => {
  await chatPage.messageInput.fill(message);
});

When("使用者點擊送出按鈕", async ({ chatPage }) => {
  await chatPage.sendButton.click();
});

Then("應顯示 AI 回覆", async ({ chatPage }) => {
  await chatPage.waitForAssistantResponse();
});
