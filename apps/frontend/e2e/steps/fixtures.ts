import { test as base, createBdd } from "playwright-bdd";
import { LoginPage } from "../pages/LoginPage";
import { ChatPage } from "../pages/ChatPage";
import { KnowledgePage } from "../pages/KnowledgePage";
import { KnowledgeDetailPage } from "../pages/KnowledgeDetailPage";
import { AppLayout } from "../pages/AppLayout";
import { BotPage } from "../pages/BotPage";
import { FeedbackPage } from "../pages/FeedbackPage";
import { SettingsPage } from "../pages/SettingsPage";

export const test = base.extend<{
  loginPage: LoginPage;
  chatPage: ChatPage;
  knowledgePage: KnowledgePage;
  knowledgeDetailPage: KnowledgeDetailPage;
  appLayout: AppLayout;
  botPage: BotPage;
  feedbackPage: FeedbackPage;
  settingsPage: SettingsPage;
}>({
  loginPage: async ({ page }, use) => {
    await use(new LoginPage(page));
  },
  chatPage: async ({ page }, use) => {
    await use(new ChatPage(page));
  },
  knowledgePage: async ({ page }, use) => {
    await use(new KnowledgePage(page));
  },
  knowledgeDetailPage: async ({ page }, use) => {
    await use(new KnowledgeDetailPage(page));
  },
  appLayout: async ({ page }, use) => {
    await use(new AppLayout(page));
  },
  botPage: async ({ page }, use) => {
    await use(new BotPage(page));
  },
  feedbackPage: async ({ page }, use) => {
    await use(new FeedbackPage(page));
  },
  settingsPage: async ({ page }, use) => {
    await use(new SettingsPage(page));
  },
});

export const { Given, When, Then, After } = createBdd(test);
