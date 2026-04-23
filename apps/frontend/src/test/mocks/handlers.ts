import { http, HttpResponse } from "msw";
import { authHandlers } from "./handlers/auth";
import { tenantHandlers } from "./handlers/tenants";
import { knowledgeBaseHandlers } from "./handlers/knowledge-bases";
import { documentHandlers } from "./handlers/documents";
import { taskHandlers } from "./handlers/tasks";
import { agentHandlers } from "./handlers/agent";
import { botHandlers } from "./handlers/bots";
import { conversationHandlers } from "./handlers/conversations";
import { feedbackHandlers } from "./handlers/feedback";
import { providerSettingHandlers } from "./handlers/provider-settings";

export const handlers = [
  http.get("http://localhost:8000/api/v1/health", () => {
    return HttpResponse.json({
      status: "healthy",
      database: "connected",
      version: "0.1.0",
    });
  }),
  ...authHandlers,
  ...tenantHandlers,
  ...knowledgeBaseHandlers,
  ...documentHandlers,
  ...taskHandlers,
  ...agentHandlers,
  ...botHandlers,
  ...conversationHandlers,
  ...feedbackHandlers,
  ...providerSettingHandlers,
];
