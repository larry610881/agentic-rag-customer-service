import { expect } from "@playwright/test";
import { Given, When, Then } from "../fixtures";

const API_BASE = process.env.API_BASE_URL ?? "http://127.0.0.1:8000/api/v1";

Given(
  "使用者已登入為 {string}",
  async ({ page }, tenantName: string) => {
    // Login via API with retry — backend may have transient DB pool issues
    let access_token = "";
    for (let attempt = 1; attempt <= 3; attempt++) {
      const res = await page.request.post(`${API_BASE}/auth/login`, {
        data: { username: tenantName, password: "password123" },
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
    // Backend uses JWT for tenant context, so switching tenant requires a new token.
    // Read current token to look up the target tenant's ID.
    const authRaw = await page.evaluate(() =>
      localStorage.getItem("auth-storage"),
    );
    const authState = JSON.parse(authRaw || "{}");
    const currentToken = authState?.state?.token;
    if (!currentToken) throw new Error("No auth token found");

    // Fetch tenants to find the target tenant's ID
    const tenantsRes = await page.request.get(`${API_BASE}/tenants`, {
      headers: { Authorization: `Bearer ${currentToken}` },
    });
    const tenants: Array<{ id: string; name: string }> =
      await tenantsRes.json();
    const target = tenants.find((t) => t.name === tenantName);
    if (!target) throw new Error(`Tenant "${tenantName}" not found`);

    // Get a new JWT token for the target tenant
    const tokenRes = await page.request.post(`${API_BASE}/auth/token`, {
      data: { tenant_id: target.id },
    });
    const { access_token } = await tokenRes.json();

    // Update localStorage with new token and tenantId so next navigation uses it
    await page.evaluate(
      ({ token, tenantId }: { token: string; tenantId: string }) => {
        localStorage.setItem(
          "auth-storage",
          JSON.stringify({
            state: { token, tenantId },
            version: 0,
          }),
        );
      },
      { token: access_token, tenantId: target.id },
    );
  },
);

Then("應包含知識庫 {string}", async ({ page }, kbName: string) => {
  await expect(page.getByText(kbName).first()).toBeVisible({ timeout: 10000 });
});

Then("不應顯示知識庫 {string}", async ({ page }, kbName: string) => {
  await expect(page.getByText(kbName)).toBeHidden();
});
