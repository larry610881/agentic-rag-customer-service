import { expect } from "@playwright/test";
import { Then, When } from "../fixtures";

Then("應顯示 AI 正在處理的指示", async ({ chatPage }) => {
  await expect(chatPage.streamingIndicator).toBeVisible({ timeout: 10000 });
});

Then("應顯示 Agent 回覆", async ({ chatPage }) => {
  await chatPage.waitForAssistantResponse();
});

Then("回覆應包含訂單狀態資訊", async ({ chatPage }) => {
  const message = await chatPage.getLastAssistantMessage();
  expect(message).toMatch(/訂單|狀態|ORD/);
});

Then("回覆應包含退貨流程說明", async ({ chatPage }) => {
  const message = await chatPage.getLastAssistantMessage();
  expect(message).toMatch(/退貨|流程|步驟/);
});

Then("回覆應包含退貨確認資訊", async ({ chatPage }) => {
  const message = await chatPage.getLastAssistantMessage();
  expect(message).toMatch(/確認|退貨|完成|成功/);
});

Then("回覆應以串流方式逐步顯示", async ({ chatPage }) => {
  await expect(chatPage.streamingIndicator).toBeVisible({ timeout: 10000 });
});

Then("最終應顯示完整的 Agent 回覆", async ({ chatPage }) => {
  await chatPage.waitForAssistantResponse();
  const message = await chatPage.getLastAssistantMessage();
  expect(message).toBeTruthy();
});

Then("回覆應顯示思考過程摺疊區塊", async ({ chatPage }) => {
  await expect(chatPage.thoughtPanel.last()).toBeVisible();
});

When("使用者點擊思考過程展開按鈕", async ({ chatPage }) => {
  await chatPage.expandThoughtPanel();
});

Then("應顯示思考過程詳情", async ({ page }) => {
  await expect(page.locator("[data-state='open']").last()).toBeVisible();
});

Then("思考過程應包含工具調用記錄", async ({ page }) => {
  const toolCalls = page.getByText(/tool|function|調用|工具/i);
  await expect(toolCalls.first()).toBeVisible();
});
