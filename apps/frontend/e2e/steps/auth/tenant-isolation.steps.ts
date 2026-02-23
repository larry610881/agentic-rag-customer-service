import { expect } from "@playwright/test";
import { Given, When, Then } from "../fixtures";

Given("使用者已登入為 {string}", async ({ loginPage }, email: string) => {
  await loginPage.goto();
  await loginPage.login(email, "password123");
});

Given("使用者在知識庫頁面", async ({ knowledgePage }) => {
  await knowledgePage.goto();
});

When(
  "使用者切換至租戶 {string}",
  async ({ appLayout }, tenantName: string) => {
    await appLayout.selectTenant(tenantName);
  },
);

Then("應包含知識庫 {string}", async ({ page }, kbName: string) => {
  await expect(page.getByText(kbName).first()).toBeVisible();
});

Then("不應顯示知識庫 {string}", async ({ page }, kbName: string) => {
  await expect(page.getByText(kbName)).toBeHidden();
});
