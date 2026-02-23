import { http, HttpResponse } from "msw";

export const handlers = [
  http.get("http://localhost:8000/api/v1/health", () => {
    return HttpResponse.json({
      status: "healthy",
      database: "connected",
      version: "0.1.0",
    });
  }),
];
