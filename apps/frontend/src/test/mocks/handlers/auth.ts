import { http, HttpResponse } from "msw";
import { mockTokenResponse } from "@/test/fixtures/auth";

export const authHandlers = [
  http.post("*/api/v1/auth/login", () => {
    return HttpResponse.json(mockTokenResponse);
  }),
];
