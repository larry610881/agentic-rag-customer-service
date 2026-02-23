import { http, HttpResponse } from "msw";
import { mockTaskResponse } from "@/test/fixtures/knowledge";

const API_BASE = "http://localhost:8000";

export const taskHandlers = [
  http.get(`${API_BASE}/api/v1/tasks/:id`, () => {
    return HttpResponse.json(mockTaskResponse);
  }),
];
