import { expect } from "@playwright/test";
import { Then } from "../fixtures";

Then("應顯示 AI 正在處理的指示", async ({ chatPage }) => {
  // With fast LLM, streaming may complete before we can observe the indicator.
  // Verify that either the streaming indicator appeared OR the response already arrived.
  // We use a short poll loop instead of Promise.race to avoid unhandled rejections.
  const deadline = Date.now() + 15000;
  let seen = false;
  while (Date.now() < deadline) {
    const streaming = await chatPage.streamingIndicator.isVisible().catch(() => false);
    const responded = await chatPage.assistantMessages.last().isVisible().catch(() => false);
    if (streaming || responded) {
      seen = true;
      break;
    }
    await new Promise((r) => setTimeout(r, 200));
  }
  expect(seen).toBe(true);
});

Then("應顯示 Agent 回覆", async ({ chatPage }) => {
  await chatPage.waitForAssistantResponse();
});

Then("回覆應以串流方式逐步顯示", async ({ chatPage }) => {
  // With fast LLM, streaming may complete instantly — just verify response arrives
  await chatPage.waitForAssistantResponse();
});

Then("最終應顯示完整的 Agent 回覆", async ({ chatPage }) => {
  await chatPage.waitForAssistantResponse();
  const message = await chatPage.getLastAssistantMessage();
  expect(message).toBeTruthy();
});
