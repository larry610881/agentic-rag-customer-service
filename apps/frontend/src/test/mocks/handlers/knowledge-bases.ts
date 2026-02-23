import { http, HttpResponse } from "msw";
import { mockKnowledgeBases } from "@/test/fixtures/knowledge";

const API_BASE = "http://localhost:8000";

export const knowledgeBaseHandlers = [
  http.get(`${API_BASE}/api/v1/knowledge-bases`, () => {
    return HttpResponse.json(mockKnowledgeBases);
  }),
  http.post(`${API_BASE}/api/v1/knowledge-bases`, async ({ request }) => {
    const body = (await request.json()) as Record<string, string>;
    return HttpResponse.json(
      {
        id: "kb-new",
        tenant_id: "tenant-1",
        name: body.name,
        description: body.description,
        document_count: 0,
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
      },
      { status: 201 },
    );
  }),
];
