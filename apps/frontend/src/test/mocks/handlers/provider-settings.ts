import { http, HttpResponse } from "msw";
import {
  mockProviderSettings,
  mockProviderSetting,
} from "@/test/fixtures/provider-setting";

const API_BASE = "http://localhost:8000";

export const providerSettingHandlers = [
  http.get(`${API_BASE}/api/v1/settings/providers`, ({ request }) => {
    const url = new URL(request.url);
    const type = url.searchParams.get("type");
    const filtered = type
      ? mockProviderSettings.filter((p) => p.provider_type === type)
      : mockProviderSettings;
    return HttpResponse.json(filtered);
  }),
  http.get(
    `${API_BASE}/api/v1/settings/providers/:id`,
    ({ params }) => {
      const setting = mockProviderSettings.find(
        (p) => p.id === params.id,
      );
      if (!setting) {
        return new HttpResponse(null, { status: 404 });
      }
      return HttpResponse.json(setting);
    },
  ),
  http.post(
    `${API_BASE}/api/v1/settings/providers`,
    async ({ request }) => {
      const body = (await request.json()) as Record<string, unknown>;
      return HttpResponse.json(
        {
          ...mockProviderSetting,
          id: "ps-new",
          display_name: body.display_name as string,
          provider_type: body.provider_type as string,
          provider_name: body.provider_name as string,
          has_api_key: true,
          created_at: new Date().toISOString(),
          updated_at: new Date().toISOString(),
        },
        { status: 201 },
      );
    },
  ),
  http.put(
    `${API_BASE}/api/v1/settings/providers/:id`,
    async ({ request, params }) => {
      const body = (await request.json()) as Record<string, unknown>;
      const existing = mockProviderSettings.find(
        (p) => p.id === params.id,
      );
      if (!existing) {
        return new HttpResponse(null, { status: 404 });
      }
      return HttpResponse.json({
        ...existing,
        ...body,
        updated_at: new Date().toISOString(),
      });
    },
  ),
  http.delete(`${API_BASE}/api/v1/settings/providers/:id`, () => {
    return new HttpResponse(null, { status: 204 });
  }),
  http.post(
    `${API_BASE}/api/v1/settings/providers/:id/test-connection`,
    () => {
      return HttpResponse.json({
        success: true,
        latency_ms: 150,
        error: "",
      });
    },
  ),
];
