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
        slug: body.slug,
        created_at: new Date().toISOString(),
      },
      { status: 201 },
    );
  }),
];
