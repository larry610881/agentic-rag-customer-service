import { http, HttpResponse } from "msw";
import { mockKnowledgeBases } from "@/test/fixtures/knowledge";

export const knowledgeBaseHandlers = [
  http.get("*/api/v1/knowledge-bases", () => {
    return HttpResponse.json({
      items: mockKnowledgeBases,
      total: mockKnowledgeBases.length,
      page: 1,
      page_size: 20,
      total_pages: 1,
    });
  }),
  http.post("*/api/v1/knowledge-bases", async ({ request }) => {
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
