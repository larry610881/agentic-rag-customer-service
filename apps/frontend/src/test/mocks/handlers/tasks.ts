import { http, HttpResponse } from "msw";
import { mockTaskResponse } from "@/test/fixtures/knowledge";

export const taskHandlers = [
  http.get("*/api/v1/tasks/:id", () => {
    return HttpResponse.json(mockTaskResponse);
  }),
];
