import { expect } from "@playwright/test";
import { Given, When, Then } from "../fixtures";

Given("使用者在登入頁面", async ({ loginPage }) => {
  await loginPage.goto();
});

When("使用者輸入帳號 {string}", async ({ loginPage }, email: string) => {
  await loginPage.usernameInput.fill(email);
});

When("使用者輸入密碼 {string}", async ({ loginPage }, password: string) => {
  await loginPage.passwordInput.fill(password);
});

When("使用者點擊登入按鈕", async ({ loginPage }) => {
  await loginPage.submitButton.click();
});

Then("應導向聊天頁面", async ({ page }) => {
  await expect(page).toHaveURL(/\/chat/);
});

Then(
  "應顯示目前租戶名稱 {string}",
  async ({ appLayout }, tenantName: string) => {
    await expect(appLayout.tenantSelector).toContainText(tenantName);
  },
);

Then(
  "應顯示帳號欄位驗證錯誤 {string}",
  async ({ page }, message: string) => {
    await expect(page.getByText(message).first()).toBeVisible();
  },
);

Then(
  "應顯示密碼欄位驗證錯誤 {string}",
  async ({ page }, message: string) => {
    await expect(page.getByText(message).first()).toBeVisible();
  },
);

Then(
  "應顯示登入失敗訊息 {string}",
  async ({ page }, message: string) => {
    await expect(page.getByText(message)).toBeVisible();
  },
);
