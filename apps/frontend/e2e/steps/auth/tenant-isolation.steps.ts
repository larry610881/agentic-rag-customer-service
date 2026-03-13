import { expect } from "@playwright/test";
import { Given, When, Then } from "../fixtures";

const API_BASE = process.env.API_BASE_URL ?? "http://127.0.0.1:8001/api/v1";

Given(
  "使用者已登入為 {string}",
  async ({ page }, tenantName: string) => {
    // Login via API with retry — backend may have transient DB pool issues
    let access_token = "";
    for (let attempt = 1; attempt <= 3; attempt++) {
      const res = await page.request.post(`${API_BASE}/auth/login`, {
        data: { account: tenantName, password: "password123" },
      });
      if (res.ok()) {
        const body = await res.json();
        access_token = body.access_token;
        break;
      }
      if (attempt === 3) {
        throw new Error(`API login failed after 3 attempts (status ${res.status()})`);
      }
      await new Promise((r) => setTimeout(r, 2000));
    }

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
  async ({ page }, tenantName: string) => {
    // Login directly as the target tenant (dev mode: account = tenant name)
    const loginRes = await page.request.post(`${API_BASE}/auth/login`, {
      data: { account: tenantName, password: "password123" },
    });
    if (!loginRes.ok()) {
      throw new Error(`Login as "${tenantName}" failed (${loginRes.status()})`);
    }
    const { access_token } = await loginRes.json();

    // Extract tenantId from JWT
    const payload = JSON.parse(
      Buffer.from(access_token.split(".")[1], "base64").toString(),
    );
    const tenantId = payload.sub;

    // Update localStorage with new token and tenantId
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

Then("應包含知識庫 {string}", async ({ page }, kbName: string) => {
  await expect(page.getByText(kbName).first()).toBeVisible({ timeout: 10000 });
});

Then("不應顯示知識庫 {string}", async ({ page }, kbName: string) => {
  await expect(page.getByText(kbName)).toBeHidden();
});
