import { request } from "@playwright/test";

const API_BASE = process.env.API_BASE_URL ?? "http://127.0.0.1:8000";
const MAX_RETRIES = 10;
const RETRY_DELAY = 2000;

/**
 * E2E Global Setup — Seeds all required data from an empty database.
 *
 * Flow (all steps are idempotent):
 *   1. Wait for backend to be ready
 *   2. Create "Demo Store" tenant          (POST /api/v1/tenants, no auth)
 *   3. Login as "Demo Store"               (POST /api/v1/auth/login)
 *   4. Create 3 knowledge bases            (POST /api/v1/knowledge-bases, auth required)
 *   5. Create "E2E 測試機器人" bot          (POST /api/v1/bots, auth required)
 *   6. Create "Other Store" tenant          (POST /api/v1/tenants, no auth)
 *   7. Register tenant admin user           (POST /api/v1/auth/register, no auth)
 */
async function globalSetup() {
  let context;
  try {
    context = await request.newContext();
  } catch (e) {
    console.warn("[E2E Setup] Could not create request context:", e);
    return;
  }

  // ── Step 1: Wait for backend to be ready ──────────────────────────
  let backendReady = false;
  for (let i = 1; i <= MAX_RETRIES; i++) {
    try {
      const healthRes = await context.get(`${API_BASE}/api/v1/tenants`);
      if (healthRes.ok()) {
        backendReady = true;
        break;
      }
      console.warn(`[E2E Setup] Attempt ${i}: Backend returned ${healthRes.status()}`);
    } catch {
      console.warn(`[E2E Setup] Attempt ${i}: Backend not reachable...`);
    }
    if (i < MAX_RETRIES)
      await new Promise((r) => setTimeout(r, RETRY_DELAY));
  }

  if (!backendReady) {
    console.warn("[E2E Setup] Backend not ready after retries. Skipping seed.");
    await context.dispose();
    return;
  }

  // ── Step 2: Ensure "Demo Store" tenant exists ─────────────────────
  const createDemoRes = await context.post(`${API_BASE}/api/v1/tenants`, {
    data: { name: "Demo Store", plan: "starter" },
  });
  if (createDemoRes.status() === 201) {
    console.log('[E2E Setup] Created tenant: "Demo Store"');
  } else if (createDemoRes.status() === 409) {
    console.log('[E2E Setup] Tenant "Demo Store" already exists, skipping.');
  } else {
    console.warn(
      `[E2E Setup] Tenant "Demo Store" creation returned ${createDemoRes.status()}`,
    );
  }

  // ── Step 3: Login as "Demo Store" → get auth token ────────────────
  const loginRes = await context.post(`${API_BASE}/api/v1/auth/login`, {
    data: { username: "Demo Store", password: "password123" },
  });
  if (!loginRes.ok()) {
    console.error(
      `[E2E Setup] Login as "Demo Store" failed (${loginRes.status()}). Cannot seed.`,
    );
    await context.dispose();
    return;
  }
  const { access_token } = await loginRes.json();
  const headers = { Authorization: `Bearer ${access_token}` };

  // Extract tenant_id from JWT (sub claim = tenant_id for tenant_access tokens)
  const jwtPayload = JSON.parse(
    Buffer.from(access_token.split(".")[1], "base64").toString(),
  );
  const demoStoreTenantId: string = jwtPayload.sub;
  console.log(`[E2E Setup] Logged in as "Demo Store" (tenant_id=${demoStoreTenantId})`);

  // ── Step 4: Ensure 3 knowledge bases exist ────────────────────────
  const kbRes = await context.get(`${API_BASE}/api/v1/knowledge-bases`, {
    headers,
  });
  const kbs: Array<{ name: string }> = kbRes.ok() ? await kbRes.json() : [];
  const existingKbNames = new Set(kbs.map((kb) => kb.name));

  const requiredKbs = [
    { name: "商品資訊", description: "所有商品的詳細規格、價格與特色說明" },
    { name: "FAQ 常見問題", description: "運費、付款、會員等常見問題" },
    { name: "退換貨政策", description: "退換貨與保固政策" },
  ];

  for (const kb of requiredKbs) {
    if (!existingKbNames.has(kb.name)) {
      const res = await context.post(`${API_BASE}/api/v1/knowledge-bases`, {
        data: kb,
        headers,
      });
      if (res.ok()) {
        console.log(`[E2E Setup] Created KB: ${kb.name}`);
      } else {
        console.warn(`[E2E Setup] KB "${kb.name}" creation returned ${res.status()}`);
      }
    }
  }

  // ── Step 5: Ensure at least one active bot exists ─────────────────
  const botsRes = await context.get(`${API_BASE}/api/v1/bots`, { headers });
  const bots: Array<{ name: string }> = botsRes.ok() ? await botsRes.json() : [];

  if (bots.length === 0) {
    // Re-fetch KBs to get their IDs
    const freshKbRes = await context.get(
      `${API_BASE}/api/v1/knowledge-bases`,
      { headers },
    );
    const freshKbs: Array<{ id: string }> = freshKbRes.ok()
      ? await freshKbRes.json()
      : [];
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
      console.warn(`[E2E Setup] Bot creation returned ${botRes.status()}`);
    }
  } else {
    console.log(
      `[E2E Setup] Bot already exists (${bots.length} bots), skipping.`,
    );
  }

  // ── Step 6: Ensure "Other Store" tenant exists ────────────────────
  const createOtherRes = await context.post(`${API_BASE}/api/v1/tenants`, {
    data: { name: "Other Store", plan: "starter" },
  });
  if (createOtherRes.status() === 201) {
    console.log('[E2E Setup] Created tenant: "Other Store"');
  } else if (createOtherRes.status() === 409) {
    console.log('[E2E Setup] Tenant "Other Store" already exists, skipping.');
  } else {
    console.warn(
      `[E2E Setup] Tenant "Other Store" creation returned ${createOtherRes.status()}`,
    );
  }

  // ── Step 7: Register tenant admin user (for journey tests J4-J8) ──
  const registerRes = await context.post(`${API_BASE}/api/v1/auth/register`, {
    data: {
      email: "admin@demo.com",
      password: "password123",
      role: "tenant_admin",
      tenant_id: demoStoreTenantId,
    },
  });
  if (registerRes.status() === 201) {
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
