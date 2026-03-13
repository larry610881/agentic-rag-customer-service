import { Given } from "../fixtures";

const API_BASE = process.env.API_BASE_URL ?? "http://127.0.0.1:8001/api/v1";

Given("租戶管理員已登入", async ({ page }) => {
  // Login via auth/login endpoint to get a user_access token
  let access_token = "";
  for (let attempt = 1; attempt <= 3; attempt++) {
    const res = await page.request.post(`${API_BASE}/auth/login`, {
      data: { account: "admin@demo.com", password: "password123" },
    });
    if (res.ok()) {
      const body = await res.json();
      access_token = body.access_token;
      break;
    }
    if (attempt === 3) {
      throw new Error(
        `Tenant admin login failed after 3 attempts (status ${res.status()})`,
      );
    }
    await new Promise((r) => setTimeout(r, 2000));
  }

  // Extract tenant_id from JWT payload
  const payload = JSON.parse(
    Buffer.from(access_token.split(".")[1], "base64").toString(),
  );

  // Navigate to app origin so we can set localStorage
  await page.goto("/login");
  await page.waitForLoadState("domcontentloaded");

  // Inject user_access token into Zustand persist storage
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
    { token: access_token, tid: payload.tenant_id },
  );

  // Reload so Zustand rehydrates from localStorage and login page auto-redirects
  await page.reload();
  await page.waitForLoadState("domcontentloaded");
});
