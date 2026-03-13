import { expect } from "@playwright/test";
import { When, Then } from "../fixtures";

When("使用者進入回饋分析頁面", async ({ feedbackPage }) => {
  await feedbackPage.goto();
});

When("使用者進入差評瀏覽器頁面", async ({ feedbackPage }) => {
  await feedbackPage.gotoBrowser();
});

Then("應顯示回饋統計摘要", async ({ page }) => {
  // FeedbackStatsSummary renders stat cards with titles
  await expect(page.getByText("總回饋數")).toBeVisible({ timeout: 10000 });
  await expect(page.getByText("滿意度", { exact: true })).toBeVisible();
});

Then("應顯示滿意度趨勢區塊", async ({ feedbackPage }) => {
  await expect(feedbackPage.trendChart).toBeVisible({ timeout: 10000 });
});

Then("應顯示 Token 用量統計區塊", async ({ feedbackPage }) => {
  await expect(feedbackPage.costTable).toBeVisible({ timeout: 10000 });
});

Then("應顯示差評瀏覽器連結", async ({ feedbackPage }) => {
  await expect(feedbackPage.browserLink).toBeVisible();
});

Then("應顯示差評瀏覽器標題", async ({ page }) => {
  await expect(
    page.getByRole("heading", { name: "差評瀏覽器" }),
  ).toBeVisible();
});

Then("應顯示回饋表格或空白狀態", async ({ page }) => {
  const content = page.locator(
    "table, :text('無符合條件的回饋'), :text('回饋瀏覽器')",
  );
  await expect(content.first()).toBeVisible({ timeout: 10000 });
});
