import { expect } from "@playwright/test";
import { Given, When, Then } from "../fixtures";

const API_BASE = process.env.API_BASE_URL ?? "http://127.0.0.1:8000/api/v1";

Given(
  "使用者已登入為 {string}",
  async ({ page }, tenantName: string) => {
    // Login via API — much faster and more reliable than UI login
    const res = await page.request.post(`${API_BASE}/auth/login`, {
      data: { username: tenantName, password: "password123" },
    });
    expect(res.ok()).toBeTruthy();
    const { access_token } = await res.json();

    // Extract tenantId from JWT payload (sub claim)
    const payload = JSON.parse(
      Buffer.from(access_token.split(".")[1], "base64").toString(),
    );
    const tenantId = payload.sub;

    // Navigate to app origin so we can set localStorage
    await page.goto("/login");
    await page.waitForLoadState("domcontentloaded");

    // Inject auth token + tenantId into Zustand persist storage
    await page.evaluate(
      ({ token, tid }: { token: string; tid: string }) => {
        localStorage.setItem(
          "auth-storage",
          JSON.stringify({
            state: { token, tenantId: tid },
            version: 0,
          }),
        );
      },
      { token: access_token, tid: tenantId },
    );
  },
);

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
  await expect(page.getByText(kbName).first()).toBeVisible({ timeout: 10000 });
});

Then("不應顯示知識庫 {string}", async ({ page }, kbName: string) => {
  await expect(page.getByText(kbName)).toBeHidden();
});
