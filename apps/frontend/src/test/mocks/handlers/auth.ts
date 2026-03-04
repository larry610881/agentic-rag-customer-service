import { http, HttpResponse } from "msw";
import { mockTokenResponse } from "@/test/fixtures/auth";

const API_BASE = "http://localhost:8000";

export const authHandlers = [
  http.post(`${API_BASE}/api/v1/auth/user-login`, () => {
    return HttpResponse.json(mockTokenResponse);
  }),
];
