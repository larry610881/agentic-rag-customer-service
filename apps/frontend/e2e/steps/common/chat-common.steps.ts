import { expect } from "@playwright/test";
import { When, Then } from "../fixtures";

When("使用者發送訊息 {string}", async ({ chatPage }, message: string) => {
  await chatPage.sendMessage(message);
  await chatPage.waitForAssistantResponse();
});

Then(
  "回覆應包含 {string} 相關內容",
  async ({ chatPage }, keyword: string) => {
    const message = await chatPage.getLastAssistantMessage();
    expect(message).toMatch(new RegExp(keyword));
  },
);

Then("應顯示引用來源區域", async ({ chatPage }) => {
  const citations = await chatPage.getCitations();
  expect(citations.length).toBeGreaterThan(0);
});

Then(
  "應顯示使用了 {string} 工具",
  async ({ chatPage }, toolName: string) => {
    const toolNames = await chatPage.getToolCallNames();
    expect(toolNames).toContain(toolName);
  },
);

Then("回覆應包含訂單狀態資訊", async ({ chatPage }) => {
  const message = await chatPage.getLastAssistantMessage();
  expect(message).toMatch(/訂單.*狀態|出貨|送達|預計/);
});

Then("回覆應要求提供訂單編號", async ({ chatPage }) => {
  const message = await chatPage.getLastAssistantMessage();
  expect(message).toMatch(/訂單編號|ORD-/);
});

Then("回覆應確認訂單並詢問退貨原因", async ({ chatPage }) => {
  const message = await chatPage.getLastAssistantMessage();
  expect(message).toMatch(/退貨原因|原因/);
});

Then("回覆應包含工單編號", async ({ chatPage }) => {
  const message = await chatPage.getLastAssistantMessage();
  expect(message).toMatch(/TK-\w+/);
});
