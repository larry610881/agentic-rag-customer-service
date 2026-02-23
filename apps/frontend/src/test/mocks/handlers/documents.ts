import { http, HttpResponse } from "msw";
import { mockUploadResponse } from "@/test/fixtures/knowledge";

const API_BASE = "http://localhost:8000";

export const documentHandlers = [
  http.post(`${API_BASE}/api/v1/documents/upload`, () => {
    return HttpResponse.json(mockUploadResponse, { status: 201 });
  }),
];
