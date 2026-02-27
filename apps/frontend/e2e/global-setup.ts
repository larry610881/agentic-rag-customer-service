import { request } from "@playwright/test";

const API_BASE = process.env.API_BASE_URL ?? "http://127.0.0.1:8000";
const MAX_RETRIES = 10;
const RETRY_DELAY = 2000;

async function globalSetup() {
  let context;
  try {
    context = await request.newContext();
  } catch (e) {
    console.warn("[E2E Setup] Could not create request context:", e);
    return;
  }

  // Wait for backend to be ready by attempting login
  let loginRes;
  for (let i = 1; i <= MAX_RETRIES; i++) {
    try {
      loginRes = await context.post(`${API_BASE}/api/v1/auth/login`, {
        data: { username: "Demo Store", password: "password123" },
      });
      if (loginRes.ok()) break;
      console.warn(
        `[E2E Setup] Attempt ${i}: Login returned ${loginRes.status()}`,
      );
    } catch {
      console.warn(`[E2E Setup] Attempt ${i}: Backend not reachable...`);
    }
    loginRes = undefined;
    if (i < MAX_RETRIES)
      await new Promise((r) => setTimeout(r, RETRY_DELAY));
  }

  if (!loginRes?.ok()) {
    console.warn("[E2E Setup] Backend not ready after retries. Skipping seed.");
    await context.dispose();
    return;
  }

  const { access_token } = await loginRes.json();
  const headers = { Authorization: `Bearer ${access_token}` };

  // Ensure required knowledge bases exist
  const kbRes = await context.get(`${API_BASE}/api/v1/knowledge-bases`, {
    headers,
  });
  const kbs: Array<{ name: string }> = await kbRes.json();
  const existingKbNames = new Set(kbs.map((kb) => kb.name));

  const requiredKbs = [
    { name: "商品資訊", description: "所有商品的詳細規格、價格與特色說明" },
    { name: "FAQ 常見問題", description: "運費、付款、會員等常見問題" },
    { name: "退換貨政策", description: "退換貨與保固政策" },
  ];

  for (const kb of requiredKbs) {
    if (!existingKbNames.has(kb.name)) {
      await context.post(`${API_BASE}/api/v1/knowledge-bases`, {
        data: kb,
        headers,
      });
      console.log(`[E2E Setup] Created KB: ${kb.name}`);
    }
  }

  // Ensure at least one active bot exists (for chat tests J3, J5)
  const botsRes = await context.get(`${API_BASE}/api/v1/bots`, { headers });
  const bots: Array<{ name: string }> = await botsRes.json();
  if (bots.length === 0) {
    // Re-fetch KBs to get their IDs
    const freshKbRes = await context.get(
      `${API_BASE}/api/v1/knowledge-bases`,
      { headers },
    );
    const freshKbs: Array<{ id: string; name: string }> =
      await freshKbRes.json();
    const kbIds = freshKbs.map((kb) => kb.id);

    const botRes = await context.post(`${API_BASE}/api/v1/bots`, {
      data: {
        name: "E2E 測試機器人",
        description: "E2E 自動化測試用機器人",
        knowledge_base_ids: kbIds,
        is_active: true,
      },
      headers,
    });
    if (botRes.ok()) {
      console.log("[E2E Setup] Created bot: E2E 測試機器人");
    } else {
      console.warn(
        `[E2E Setup] Bot creation returned ${botRes.status()}`,
      );
    }
  } else {
    console.log(`[E2E Setup] Bot already exists (${bots.length} bots), skipping.`);
  }

  // Ensure "Other Store" tenant exists (for tenant-isolation test)
  const tenantsRes = await context.get(`${API_BASE}/api/v1/tenants`, {
    headers,
  });
  const tenants: Array<{ name: string }> = await tenantsRes.json();
  const tenantNames = new Set(tenants.map((t) => t.name));

  if (!tenantNames.has("Other Store")) {
    await context.post(`${API_BASE}/api/v1/tenants`, {
      data: { name: "Other Store", slug: "other-store" },
      headers,
    });
    console.log("[E2E Setup] Created tenant: Other Store");
  }

  // Register a tenant admin user for journey tests (J4-J8)
  // Extract tenant_id from the JWT (sub claim = tenant_id for tenant_access tokens)
  const jwtPayload = JSON.parse(
    Buffer.from(access_token.split(".")[1], "base64").toString(),
  );
  const demoStoreTenantId = jwtPayload.sub;

  const registerRes = await context.post(`${API_BASE}/api/v1/auth/register`, {
    data: {
      email: "admin@demo.com",
      password: "password123",
      role: "tenant_admin",
      tenant_id: demoStoreTenantId,
    },
    headers,
  });
  if (registerRes.ok()) {
    console.log("[E2E Setup] Registered tenant admin: admin@demo.com");
  } else if (
    registerRes.status() === 409 ||
    registerRes.status() === 400
  ) {
    console.log("[E2E Setup] Tenant admin already exists, skipping.");
  } else {
    console.warn(
      `[E2E Setup] Tenant admin registration returned ${registerRes.status()}`,
    );
  }

  await context.dispose();
  console.log("[E2E Setup] Seed complete.");
}

export default globalSetup;
