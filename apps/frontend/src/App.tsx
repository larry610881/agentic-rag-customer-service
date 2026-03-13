import { lazy, Suspense } from "react";
import { Navigate, Route, Routes } from "react-router-dom";
import { ROUTES } from "@/routes/paths";
import { AdminRoute, ProtectedRoute } from "@/components/layout/protected-route";
import { AppShell } from "@/components/layout/app-shell";

const LoginPage = lazy(() => import("@/pages/login"));
const ChatPage = lazy(() => import("@/pages/chat"));
const BotsPage = lazy(() => import("@/pages/bots"));
const BotDetailPage = lazy(() => import("@/pages/bot-detail"));
const KnowledgePage = lazy(() => import("@/pages/knowledge"));
const KnowledgeDetailPage = lazy(() => import("@/pages/knowledge-detail"));
const FeedbackPage = lazy(() => import("@/pages/feedback"));
const FeedbackBrowserPage = lazy(() => import("@/pages/feedback-browser"));
const FeedbackConversationPage = lazy(
  () => import("@/pages/feedback-conversation"),
);
const ProvidersSettingsPage = lazy(() => import("@/pages/settings-providers"));
const AdminLogsPage = lazy(() => import("@/pages/admin-logs"));
const AdminKnowledgeBasesPage = lazy(
  () => import("@/pages/admin-knowledge-bases"),
);
const AdminBotsPage = lazy(() => import("@/pages/admin-bots"));
const AdminKbDetailPage = lazy(() => import("@/pages/admin-kb-detail"));
const AdminBotDetailPage = lazy(() => import("@/pages/admin-bot-detail"));
const AdminUsersPage = lazy(() => import("@/pages/admin-users"));
const AdminObservabilityPage = lazy(() => import("@/pages/admin-observability"));
const AdminTokenUsagePage = lazy(() => import("@/pages/admin-token-usage"));
const AdminMcpRegistryPage = lazy(() => import("@/pages/admin-mcp-registry"));
const AdminTenantsPage = lazy(() => import("@/pages/admin-tenants"));
const AdminPromptsPage = lazy(() => import("@/pages/admin-prompts"));
const AdminDiagnosticRulesPage = lazy(() => import("@/pages/admin-diagnostic-rules"));
const AdminRateLimitsPage = lazy(() => import("@/pages/admin-rate-limits"));
const AdminLogRetentionPage = lazy(() => import("@/pages/admin-log-retention"));

function PageFallback() {
  return (
    <div className="flex h-full items-center justify-center">
      <p className="text-muted-foreground">載入中...</p>
    </div>
  );
}

export function App() {
  return (
    <Suspense fallback={<PageFallback />}>
      <Routes>
        <Route path={ROUTES.LOGIN} element={<LoginPage />} />

        <Route element={<ProtectedRoute />}>
          <Route element={<AppShell />}>
            <Route path={ROUTES.CHAT} element={<ChatPage />} />
            <Route path={ROUTES.BOTS} element={<BotsPage />} />
            <Route path={ROUTES.BOT_DETAIL} element={<BotDetailPage />} />
            <Route path={ROUTES.KNOWLEDGE} element={<KnowledgePage />} />
            <Route
              path={ROUTES.KNOWLEDGE_DETAIL}
              element={<KnowledgeDetailPage />}
            />
            <Route path={ROUTES.FEEDBACK} element={<FeedbackPage />} />
            <Route
              path={ROUTES.FEEDBACK_BROWSER}
              element={<FeedbackBrowserPage />}
            />
            <Route
              path={ROUTES.FEEDBACK_CONVERSATION}
              element={<FeedbackConversationPage />}
            />
          </Route>
        </Route>

        <Route element={<AdminRoute />}>
          <Route element={<AppShell />}>
            <Route
              path={ROUTES.SETTINGS}
              element={<Navigate to={ROUTES.SETTINGS_PROVIDERS} replace />}
            />
            <Route
              path={ROUTES.SETTINGS_PROVIDERS}
              element={<ProvidersSettingsPage />}
            />
            <Route path={ROUTES.ADMIN_LOGS} element={<AdminLogsPage />} />
            <Route
              path={ROUTES.ADMIN_KNOWLEDGE_BASES}
              element={<AdminKnowledgeBasesPage />}
            />
            <Route
              path={ROUTES.ADMIN_KB_DETAIL}
              element={<AdminKbDetailPage />}
            />
            <Route path={ROUTES.ADMIN_BOTS} element={<AdminBotsPage />} />
            <Route
              path={ROUTES.ADMIN_BOT_DETAIL}
              element={<AdminBotDetailPage />}
            />
            <Route path={ROUTES.ADMIN_USERS} element={<AdminUsersPage />} />
            <Route
              path={ROUTES.ADMIN_OBSERVABILITY}
              element={<AdminObservabilityPage />}
            />
            <Route
              path={ROUTES.ADMIN_TOKEN_USAGE}
              element={<AdminTokenUsagePage />}
            />
            <Route
              path={ROUTES.ADMIN_MCP_REGISTRY}
              element={<AdminMcpRegistryPage />}
            />
            <Route
              path={ROUTES.ADMIN_TENANTS}
              element={<AdminTenantsPage />}
            />
            <Route
              path={ROUTES.ADMIN_PROMPTS}
              element={<AdminPromptsPage />}
            />
            <Route
              path={ROUTES.ADMIN_DIAGNOSTIC_RULES}
              element={<AdminDiagnosticRulesPage />}
            />
            <Route
              path={ROUTES.ADMIN_RATE_LIMITS}
              element={<AdminRateLimitsPage />}
            />
            <Route
              path={ROUTES.ADMIN_LOG_RETENTION}
              element={<AdminLogRetentionPage />}
            />
          </Route>
        </Route>

        <Route
          path={ROUTES.HOME}
          element={<Navigate to={ROUTES.CHAT} replace />}
        />
        <Route path="*" element={<Navigate to={ROUTES.CHAT} replace />} />
      </Routes>
    </Suspense>
  );
}
