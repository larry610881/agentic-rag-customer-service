import { http, HttpResponse } from "msw";
import { mockTenants } from "@/test/fixtures/auth";

const API_BASE = "http://localhost:8000";

export const tenantHandlers = [
  http.get(`${API_BASE}/api/v1/tenants`, () => {
    return HttpResponse.json(mockTenants);
  }),
  http.post(`${API_BASE}/api/v1/tenants`, async ({ request }) => {
    const body = (await request.json()) as Record<string, string>;
    return HttpResponse.json(
      {
        id: "tenant-new",
        name: body.name,
        plan: body.plan || "starter",
        allowed_agent_modes: ["router"],
        allowed_widget_avatar: false,
        monthly_token_limit: null,
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
      },
      { status: 201 },
    );
  }),
  http.patch(`${API_BASE}/api/v1/tenants/:tenantId/agent-modes`, async ({ request, params }) => {
    const body = (await request.json()) as { allowed_agent_modes: string[] };
    const tenant = mockTenants.find((t) => t.id === params.tenantId);
    if (!tenant) return new HttpResponse(null, { status: 404 });
    return HttpResponse.json({
      ...tenant,
      allowed_agent_modes: body.allowed_agent_modes,
      updated_at: new Date().toISOString(),
    });
  }),
  http.patch(`${API_BASE}/api/v1/tenants/:tenantId/widget-avatar`, async ({ request, params }) => {
    const body = (await request.json()) as { allowed_widget_avatar: boolean };
    const tenant = mockTenants.find((t) => t.id === params.tenantId);
    if (!tenant) return new HttpResponse(null, { status: 404 });
    return HttpResponse.json({
      ...tenant,
      allowed_widget_avatar: body.allowed_widget_avatar,
      updated_at: new Date().toISOString(),
    });
  }),
  http.patch(`${API_BASE}/api/v1/tenants/:tenantId/config`, async ({ request, params }) => {
    const body = (await request.json()) as { monthly_token_limit: number | null };
    const tenant = mockTenants.find((t) => t.id === params.tenantId);
    if (!tenant) return new HttpResponse(null, { status: 404 });
    return HttpResponse.json({
      ...tenant,
      monthly_token_limit: body.monthly_token_limit,
      updated_at: new Date().toISOString(),
    });
  }),
];
