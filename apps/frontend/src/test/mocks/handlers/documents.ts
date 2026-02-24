import { http, HttpResponse } from "msw";
import { mockDocuments, mockUploadResponse } from "@/test/fixtures/knowledge";

const API_BASE = "http://localhost:8000";

export const documentHandlers = [
  http.get(`${API_BASE}/api/v1/knowledge-bases/:kbId/documents`, () => {
    return HttpResponse.json(mockDocuments);
  }),

  http.delete(`${API_BASE}/api/v1/knowledge-bases/:kbId/documents/:docId`, () => {
    return new HttpResponse(null, { status: 204 });
  }),

  http.post(`${API_BASE}/api/v1/knowledge-bases/:kbId/documents`, () => {
    return HttpResponse.json(mockUploadResponse, { status: 201 });
  }),
];
