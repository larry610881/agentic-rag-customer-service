import { test as base, createBdd } from "playwright-bdd";
import { LoginPage } from "../pages/LoginPage";
import { ChatPage } from "../pages/ChatPage";
import { KnowledgePage } from "../pages/KnowledgePage";
import { KnowledgeDetailPage } from "../pages/KnowledgeDetailPage";
import { AppLayout } from "../pages/AppLayout";

export const test = base.extend<{
  loginPage: LoginPage;
  chatPage: ChatPage;
  knowledgePage: KnowledgePage;
  knowledgeDetailPage: KnowledgeDetailPage;
  appLayout: AppLayout;
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
});

export const { Given, When, Then } = createBdd(test);
