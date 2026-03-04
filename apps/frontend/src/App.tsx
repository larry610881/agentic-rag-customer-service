import { lazy, Suspense } from "react";
import { Navigate, Route, Routes } from "react-router-dom";
import { ROUTES } from "@/routes/paths";
import { ProtectedRoute } from "@/components/layout/protected-route";
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
            <Route
              path={ROUTES.SETTINGS}
              element={<Navigate to={ROUTES.SETTINGS_PROVIDERS} replace />}
            />
            <Route
              path={ROUTES.SETTINGS_PROVIDERS}
              element={<ProvidersSettingsPage />}
            />
            <Route
              path={ROUTES.ADMIN_LOGS}
              element={<AdminLogsPage />}
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
