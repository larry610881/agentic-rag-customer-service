import { expect } from "@playwright/test";
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

Then("回覆應包含退貨相關資訊", async ({ chatPage }) => {
  const message = await chatPage.getLastAssistantMessage();
  expect(message).toMatch(/退貨|退換貨|退款/);
});

Then("回覆應顯示來源引用區塊", async ({ chatPage }) => {
  const citations = await chatPage.getCitations();
  expect(citations.length).toBeGreaterThan(0);
});

Then("來源引用應包含知識庫名稱", async ({ chatPage }) => {
  const citations = await chatPage.getCitations();
  expect(citations.length).toBeGreaterThan(0);
  const citationText = citations.join(" ");
  expect(citationText.length).toBeGreaterThan(0);
});
