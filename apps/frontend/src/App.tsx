import { type ComponentType, lazy, Suspense } from "react";
import { Navigate, Route, Routes } from "react-router-dom";
import { ROUTES } from "@/routes/paths";
import { AdminRoute, ProtectedRoute } from "@/components/layout/protected-route";
import { AppShell } from "@/components/layout/app-shell";

/**
 * Retry dynamic import once on chunk load failure (common after deployment).
 * Marks sessionStorage to avoid infinite reload loops.
 */
function lazyWithRetry(factory: () => Promise<{ default: ComponentType }>) {
  return lazy(() =>
    factory().catch((err: unknown) => {
      const key = "chunk_reload_" + factory.toString().slice(0, 64);
      if (!sessionStorage.getItem(key)) {
        sessionStorage.setItem(key, "1");
        window.location.reload();
        // Return a never-resolving promise so React doesn't render stale error
        return new Promise(() => {});
      }
      throw err;
    }),
  );
}

const LoginPage = lazyWithRetry(() => import("@/pages/login"));
const ChatPage = lazyWithRetry(() => import("@/pages/chat"));
const BotsPage = lazyWithRetry(() => import("@/pages/bots"));
const BotDetailPage = lazyWithRetry(() => import("@/pages/bot-detail"));
const BotStudioPage = lazyWithRetry(() => import("@/pages/bot-studio"));
const KnowledgePage = lazyWithRetry(() => import("@/pages/knowledge"));
const KnowledgeDetailPage = lazyWithRetry(() => import("@/pages/knowledge-detail"));
const FeedbackPage = lazyWithRetry(() => import("@/pages/feedback"));
const TokenUsagePage = lazyWithRetry(() => import("@/pages/token-usage"));
const FeedbackBrowserPage = lazyWithRetry(() => import("@/pages/feedback-browser"));
const FeedbackConversationPage = lazy(
  () => import("@/pages/feedback-conversation"),
);
const ProvidersSettingsPage = lazyWithRetry(() => import("@/pages/settings-providers"));
const AdminLogsPage = lazyWithRetry(() => import("@/pages/admin-logs"));
const AdminKnowledgeBasesPage = lazy(
  () => import("@/pages/admin-knowledge-bases"),
);
const AdminBotsPage = lazyWithRetry(() => import("@/pages/admin-bots"));
const AdminKbDetailPage = lazyWithRetry(() => import("@/pages/admin-kb-detail"));
const AdminBotDetailPage = lazyWithRetry(() => import("@/pages/admin-bot-detail"));
const AdminUsersPage = lazyWithRetry(() => import("@/pages/admin-users"));
const AdminObservabilityPage = lazyWithRetry(() => import("@/pages/admin-observability"));
const AdminTokenUsagePage = lazyWithRetry(() => import("@/pages/admin-token-usage"));
const AdminMcpRegistryPage = lazyWithRetry(() => import("@/pages/admin-mcp-registry"));
const AdminToolsPage = lazyWithRetry(() => import("@/pages/admin-tools"));
const AdminTenantsPage = lazyWithRetry(() => import("@/pages/admin-tenants"));
const AdminPlansPage = lazyWithRetry(() => import("@/pages/admin-plans"));
const AdminPromptsPage = lazyWithRetry(() => import("@/pages/admin-prompts"));
const AdminGuardRulesPage = lazyWithRetry(() => import("@/pages/admin-guard-rules"));
const AdminDiagnosticRulesPage = lazyWithRetry(() => import("@/pages/admin-diagnostic-rules"));
const AdminRateLimitsPage = lazyWithRetry(() => import("@/pages/admin-rate-limits"));
const AdminLogRetentionPage = lazyWithRetry(() => import("@/pages/admin-log-retention"));
const AdminErrorEventsPage = lazyWithRetry(() => import("@/pages/admin-error-events"));
const AdminNotificationChannelsPage = lazyWithRetry(() => import("@/pages/admin-notification-channels"));
const AdminPromptOptimizerPage = lazyWithRetry(() => import("@/pages/admin-prompt-optimizer"));
const AdminPromptOptimizerStartPage = lazyWithRetry(() => import("@/pages/admin-prompt-optimizer-start"));
const AdminPromptOptimizerDatasetsPage = lazyWithRetry(() => import("@/pages/admin-prompt-optimizer-datasets"));
const AdminPromptOptimizerDatasetNewPage = lazyWithRetry(() => import("@/pages/admin-prompt-optimizer-dataset-new"));
const AdminPromptOptimizerDatasetEditPage = lazyWithRetry(() => import("@/pages/admin-prompt-optimizer-dataset-edit"));
const AdminPromptOptimizerRunsPage = lazyWithRetry(() => import("@/pages/admin-prompt-optimizer-runs"));
const AdminPromptOptimizerRunDetailPage = lazyWithRetry(() => import("@/pages/admin-prompt-optimizer-run-detail"));
const AdminPromptOptimizerValidatePage = lazyWithRetry(() => import("@/pages/admin-prompt-optimizer-validate"));

function PageFallback() {
  return (
    <div className="flex h-full items-center justify-center">
      <p className="text-muted-foreground">載入中...</p>
    </div>
  );
}

export function App() {
  return (
    <Routes>
      <Route
        path={ROUTES.LOGIN}
        element={
          <Suspense fallback={<PageFallback />}>
            <LoginPage />
          </Suspense>
        }
      />

        <Route element={<ProtectedRoute />}>
          <Route element={<AppShell />}>
            <Route path={ROUTES.CHAT} element={<ChatPage />} />
            <Route path={ROUTES.BOTS} element={<BotsPage />} />
            <Route path={ROUTES.BOT_DETAIL} element={<BotDetailPage />} />
            <Route path={ROUTES.BOT_STUDIO} element={<BotStudioPage />} />
            <Route path={ROUTES.KNOWLEDGE} element={<KnowledgePage />} />
            <Route
              path={ROUTES.KNOWLEDGE_DETAIL}
              element={<KnowledgeDetailPage />}
            />
            <Route path={ROUTES.FEEDBACK} element={<FeedbackPage />} />
            <Route path={ROUTES.TOKEN_USAGE} element={<TokenUsagePage />} />
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
              path={ROUTES.ADMIN_TOOLS}
              element={<AdminToolsPage />}
            />
            <Route
              path={ROUTES.ADMIN_TENANTS}
              element={<AdminTenantsPage />}
            />
            <Route
              path={ROUTES.ADMIN_PLANS}
              element={<AdminPlansPage />}
            />
            <Route
              path={ROUTES.ADMIN_PROMPTS}
              element={<AdminPromptsPage />}
            />
            <Route
              path="/admin/guard-rules"
              element={<AdminGuardRulesPage />}
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
            <Route
              path={ROUTES.ADMIN_ERROR_EVENTS}
              element={<AdminErrorEventsPage />}
            />
            <Route
              path={ROUTES.ADMIN_NOTIFICATION_CHANNELS}
              element={<AdminNotificationChannelsPage />}
            />
            <Route
              path={ROUTES.ADMIN_PROMPT_OPTIMIZER}
              element={<AdminPromptOptimizerPage />}
            />
            <Route
              path={ROUTES.ADMIN_PROMPT_OPTIMIZER_START}
              element={<AdminPromptOptimizerStartPage />}
            />
            <Route
              path={ROUTES.ADMIN_PROMPT_OPTIMIZER_DATASETS}
              element={<AdminPromptOptimizerDatasetsPage />}
            />
            <Route
              path={ROUTES.ADMIN_PROMPT_OPTIMIZER_DATASET_NEW}
              element={<AdminPromptOptimizerDatasetNewPage />}
            />
            <Route
              path={ROUTES.ADMIN_PROMPT_OPTIMIZER_DATASET_EDIT}
              element={<AdminPromptOptimizerDatasetEditPage />}
            />
            <Route
              path={ROUTES.ADMIN_PROMPT_OPTIMIZER_RUNS}
              element={<AdminPromptOptimizerRunsPage />}
            />
            <Route
              path={ROUTES.ADMIN_PROMPT_OPTIMIZER_RUN_DETAIL}
              element={<AdminPromptOptimizerRunDetailPage />}
            />
            <Route
              path={ROUTES.ADMIN_PROMPT_OPTIMIZER_VALIDATE}
              element={<AdminPromptOptimizerValidatePage />}
            />
          </Route>
        </Route>

        <Route
          path={ROUTES.HOME}
          element={<Navigate to={ROUTES.CHAT} replace />}
        />
        <Route path="*" element={<Navigate to={ROUTES.CHAT} replace />} />
      </Routes>
  );
}
