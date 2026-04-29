import { expect } from "@playwright/test";
import { Given, When, Then } from "../fixtures";

// 從 URL 抽 KB id（前一個 step「點擊知識庫商品資訊」會把 user 帶到 /knowledge/<id>）
function kbIdFromUrl(url: string): string {
  const m = url.match(/\/knowledge\/([^/?]+)/);
  return m ? m[1] : "";
}

Given("使用者導航至該知識庫的 KB Studio", async ({ page }) => {
  const kbId = kbIdFromUrl(page.url());
  expect(kbId, "expect /knowledge/:id URL before navigating").not.toBe("");
  await page.goto(`/admin/kb-studio/${kbId}`);
  // 等 page header 載入
  await expect(
    page.getByRole("heading", { name: "KB Studio" }),
  ).toBeVisible({ timeout: 10000 });
});

Then(
  "應顯示 5 個 tab {string} {string} {string} {string} {string}",
  async (
    { page },
    t1: string,
    t2: string,
    t3: string,
    t4: string,
    t5: string,
  ) => {
    for (const label of [t1, t2, t3, t4, t5]) {
      await expect(
        page.getByRole("button", { name: label }),
      ).toBeVisible();
    }
  },
);

Then(
  "預設選中的 tab 應為 {string}",
  async ({ page }, label: string) => {
    // 選中的 tab 用 font-semibold + border-primary class（kb-studio-tabs.tsx）
    const activeTab = page
      .locator("button")
      .filter({ hasText: label })
      .first();
    await expect(activeTab).toHaveClass(/font-semibold/);
  },
);

When("使用者切換到 {string} tab", async ({ page }, label: string) => {
  await page.getByRole("button", { name: label }).click();
});

Then("應顯示 KB 名稱輸入欄位", async ({ page }) => {
  await expect(page.getByLabel("名稱")).toBeVisible();
});

Then("應顯示 OCR 模式選擇器", async ({ page }) => {
  await expect(page.getByLabel("OCR 模式")).toBeVisible();
});

Then("應顯示 OCR 解析模型選擇器", async ({ page }) => {
  await expect(page.getByLabel("OCR 解析")).toBeVisible();
});

Then("應顯示上下文生成模型選擇器", async ({ page }) => {
  await expect(
    page.getByLabel(/上下文生成/),
  ).toBeVisible();
});

Then("應顯示自動分類模型選擇器", async ({ page }) => {
  await expect(page.getByLabel("自動分類")).toBeVisible();
});

When(
  "使用者開啟 KB Studio 並使用舊參數 {string}",
  async ({ page }, query: string) => {
    const kbId = kbIdFromUrl(page.url());
    await page.goto(`/admin/kb-studio/${kbId}${query}`);
    await expect(
      page.getByRole("heading", { name: "KB Studio" }),
    ).toBeVisible({ timeout: 10000 });
  },
);

Then(
  "應顯示文件統計卡片 {string}",
  async ({ page }, label: string) => {
    // page header HeaderStats 渲染：StatCard label 文字 + 數字
    const card = page.getByText(label, { exact: true }).first();
    await expect(card).toBeVisible({ timeout: 5000 });
  },
);

When(
  "使用者點擊任一已處理文件的「查看分塊」按鈕",
  async ({ page }) => {
    // 等文件列表載入；找第一個「查看分塊」button（已處理 + 有 chunks 的才會顯示）
    const viewChunksBtn = page
      .getByRole("button", { name: /查看分塊/ })
      .first();
    await expect(viewChunksBtn).toBeVisible({ timeout: 15000 });
    await viewChunksBtn.click();
  },
);

Then("應顯示分塊編輯對話框", async ({ page }) => {
  await expect(page.getByRole("dialog")).toBeVisible({ timeout: 5000 });
});

Then(
  "對話框標題應包含 {string}",
  async ({ page }, expected: string) => {
    // chunkEditable=true 時 DialogTitle 是「{filename} — 分塊編輯」
    const title = page.getByRole("dialog").locator("h2,h3").first();
    await expect(title).toContainText(expected);
  },
);
