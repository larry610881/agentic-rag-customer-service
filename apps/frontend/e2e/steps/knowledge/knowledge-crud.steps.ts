import { expect } from "@playwright/test";
import { Given, When, Then } from "../fixtures";

Then("應顯示知識庫列表", async ({ knowledgePage }) => {
  await expect(knowledgePage.kbList).toBeVisible();
});

When(
  "使用者點擊知識庫 {string}",
  async ({ knowledgePage }, kbName: string) => {
    await knowledgePage.clickKnowledgeBase(kbName);
  },
);

Then(
  "應顯示知識庫名稱 {string}",
  async ({ page }, kbName: string) => {
    await expect(page.getByRole("heading", { name: kbName })).toBeVisible();
  },
);

Then("應顯示文件列表", async ({ knowledgeDetailPage }) => {
  await expect(knowledgeDetailPage.documentList).toBeVisible();
});

Then("每個文件應顯示名稱與狀態", async ({ knowledgeDetailPage }) => {
  const documents = await knowledgeDetailPage.getDocuments();
  expect(documents.length).toBeGreaterThan(0);
  for (const doc of documents) {
    expect(doc.name).toBeTruthy();
    expect(doc.status).toBeTruthy();
  }
});
