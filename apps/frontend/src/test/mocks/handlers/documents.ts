import { http, HttpResponse } from "msw";
import { mockDocuments, mockUploadResponse } from "@/test/fixtures/knowledge";

export const documentHandlers = [
  http.get("*/api/v1/knowledge-bases/:kbId/documents", () => {
    return HttpResponse.json({
      items: mockDocuments,
      total: mockDocuments.length,
      page: 1,
      page_size: 20,
      total_pages: 1,
    });
  }),

  http.delete("*/api/v1/knowledge-bases/:kbId/documents/:docId", () => {
    return new HttpResponse(null, { status: 204 });
  }),

  http.post("*/api/v1/knowledge-bases/:kbId/documents", () => {
    return HttpResponse.json(mockUploadResponse, { status: 201 });
  }),
];
