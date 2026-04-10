import { describe, it, expect, vi, beforeEach } from "vitest";
import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { renderWithProviders } from "@/test/test-utils";
import { BotDetailForm } from "@/features/bot/components/bot-detail-form";
import { mockBot } from "@/test/fixtures/bot";
import { useAuthStore } from "@/stores/use-auth-store";

describe("BotDetailForm", () => {
  const mockOnSave = vi.fn();
  const mockOnDelete = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
    useAuthStore.setState({
      token: "test-token",
      tenantId: "tenant-1",
      tenants: [
        {
          id: "tenant-1",
          name: "Test Tenant",
          plan: "pro",
          monthly_token_limit: null,
          created_at: "2024-01-01T00:00:00Z",
          updated_at: "2024-01-01T00:00:00Z",
        },
      ],
    });
  });

  it("should render bot name input with current value", () => {
    renderWithProviders(
      <BotDetailForm
        bot={mockBot}
        onSave={mockOnSave}
        onDelete={mockOnDelete}
        isSaving={false}
        isDeleting={false}
      />,
    );
    const nameInput = screen.getByLabelText("名稱");
    expect(nameInput).toHaveValue("Customer Service Bot");
  });

  it("should render LLM parameter inputs in LLM tab", async () => {
    const user = userEvent.setup();
    renderWithProviders(
      <BotDetailForm
        bot={mockBot}
        onSave={mockOnSave}
        onDelete={mockOnDelete}
        isSaving={false}
        isDeleting={false}
      />,
    );
    await user.click(screen.getByRole("tab", { name: "LLM 參數" }));
    expect(screen.getByLabelText("溫度（0-1）")).toHaveValue(0.3);
    expect(screen.getByLabelText("最大 Token 數（128-4096）")).toHaveValue(1024);
    expect(screen.getByLabelText("歷史訊息數（0-35）")).toHaveValue(10);
  });

  it("should render system prompt textarea in prompt tab", async () => {
    const user = userEvent.setup();
    renderWithProviders(
      <BotDetailForm
        bot={mockBot}
        onSave={mockOnSave}
        onDelete={mockOnDelete}
        isSaving={false}
        isDeleting={false}
      />,
    );
    await user.click(screen.getByRole("tab", { name: "系統提示詞" }));
    expect(screen.getByLabelText("Bot 自訂指令")).toHaveValue(
      "You are a helpful customer service bot.",
    );
  });

  it("should render LINE channel fields in LINE tab", async () => {
    const user = userEvent.setup();
    renderWithProviders(
      <BotDetailForm
        bot={mockBot}
        onSave={mockOnSave}
        onDelete={mockOnDelete}
        isSaving={false}
        isDeleting={false}
      />,
    );
    await user.click(screen.getByRole("tab", { name: "LINE 頻道" }));
    expect(screen.getByLabelText("頻道密鑰")).toBeInTheDocument();
    expect(screen.getByLabelText("存取權杖")).toBeInTheDocument();
  });

  it("should render enabled tools checkboxes in knowledge tab", () => {
    renderWithProviders(
      <BotDetailForm
        bot={mockBot}
        onSave={mockOnSave}
        onDelete={mockOnDelete}
        isSaving={false}
        isDeleting={false}
      />,
    );
    expect(screen.getByLabelText("知識庫查詢（預設啟用）")).toBeChecked();
  });

  it("should render save and delete buttons", () => {
    renderWithProviders(
      <BotDetailForm
        bot={mockBot}
        onSave={mockOnSave}
        onDelete={mockOnDelete}
        isSaving={false}
        isDeleting={false}
      />,
    );
    expect(
      screen.getByRole("button", { name: "儲存變更" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "刪除機器人" }),
    ).toBeInTheDocument();
  });

  it("should show loading state when saving", () => {
    renderWithProviders(
      <BotDetailForm
        bot={mockBot}
        onSave={mockOnSave}
        onDelete={mockOnDelete}
        isSaving={true}
        isDeleting={false}
      />,
    );
    expect(
      screen.getByRole("button", { name: "儲存中..." }),
    ).toBeDisabled();
  });

  it("should show loading state when deleting", () => {
    renderWithProviders(
      <BotDetailForm
        bot={mockBot}
        onSave={mockOnSave}
        onDelete={mockOnDelete}
        isSaving={false}
        isDeleting={true}
      />,
    );
    expect(
      screen.getByRole("button", { name: "刪除中..." }),
    ).toBeDisabled();
  });

  it("should show FAB icon upload section in Widget tab", async () => {
    const user = userEvent.setup();
    renderWithProviders(
      <BotDetailForm
        bot={mockBot}
        onSave={mockOnSave}
        onDelete={mockOnDelete}
        isSaving={false}
        isDeleting={false}
      />,
    );
    await user.click(screen.getByRole("tab", { name: "Widget" }));
    expect(screen.getByText("FAB 按鈕圖示")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /上傳圖片/ })).toBeInTheDocument();
  });

  it("should show placeholder when no icon uploaded", async () => {
    const user = userEvent.setup();
    renderWithProviders(
      <BotDetailForm
        bot={mockBot}
        onSave={mockOnSave}
        onDelete={mockOnDelete}
        isSaving={false}
        isDeleting={false}
      />,
    );
    await user.click(screen.getByRole("tab", { name: "Widget" }));
    expect(screen.getByText("尚未上傳自訂圖示")).toBeInTheDocument();
  });

  it("should render Widget tab content without avatar section", async () => {
    const user = userEvent.setup();
    renderWithProviders(
      <BotDetailForm
        bot={mockBot}
        onSave={mockOnSave}
        onDelete={mockOnDelete}
        isSaving={false}
        isDeleting={false}
      />,
    );
    await user.click(screen.getByRole("tab", { name: "Widget" }));
    expect(screen.getByText("Web Widget")).toBeInTheDocument();
    expect(screen.getByText("允許來源")).toBeInTheDocument();
    expect(screen.getByText("對話歷史")).toBeInTheDocument();
    expect(screen.queryByText("Avatar 角色選擇")).not.toBeInTheDocument();
    expect(screen.getByText("Widget 文字設定")).toBeInTheDocument();
    expect(screen.getByText("嵌入碼")).toBeInTheDocument();
  });

  // ==========================================================================
  // Sprint W.4 — Knowledge Mode (Wiki vs RAG)
  // ==========================================================================

  it("should default to RAG mode and show multi-select KB checkboxes", () => {
    renderWithProviders(
      <BotDetailForm
        bot={mockBot}
        onSave={mockOnSave}
        onDelete={mockOnDelete}
        isSaving={false}
        isDeleting={false}
      />,
    );
    expect(screen.getByLabelText("知識模式")).toBeInTheDocument();
    expect(screen.getByText("已綁定的知識庫（可多選）")).toBeInTheDocument();
    expect(screen.queryByTestId("compile-wiki-card")).not.toBeInTheDocument();
  });

  it("should show CompileWikiCard and single KB Select when switched to Wiki mode", async () => {
    const user = userEvent.setup();
    renderWithProviders(
      <BotDetailForm
        bot={{ ...mockBot, knowledge_mode: "wiki" }}
        onSave={mockOnSave}
        onDelete={mockOnDelete}
        isSaving={false}
        isDeleting={false}
      />,
    );
    // Wiki section should be visible
    expect(screen.getByText("Wiki 知識庫")).toBeInTheDocument();
    expect(screen.getByLabelText("綁定知識庫")).toBeInTheDocument();
    expect(screen.getByLabelText("導航策略")).toBeInTheDocument();
    expect(screen.getByTestId("compile-wiki-card")).toBeInTheDocument();
    // RAG-specific UI should be hidden
    expect(
      screen.queryByText("已綁定的知識庫（可多選）"),
    ).not.toBeInTheDocument();
    // Avoid unused var warning
    void user;
  });

  it("should hide RAG params when in Wiki mode", () => {
    renderWithProviders(
      <BotDetailForm
        bot={{ ...mockBot, knowledge_mode: "wiki" }}
        onSave={mockOnSave}
        onDelete={mockOnDelete}
        isSaving={false}
        isDeleting={false}
      />,
    );
    // RAG params section should not exist in wiki mode
    expect(screen.queryByLabelText("Top K（1-20）")).not.toBeInTheDocument();
  });

  it("should default wiki_navigation_strategy to keyword_bfs", () => {
    renderWithProviders(
      <BotDetailForm
        bot={{ ...mockBot, knowledge_mode: "wiki" }}
        onSave={mockOnSave}
        onDelete={mockOnDelete}
        isSaving={false}
        isDeleting={false}
      />,
    );
    // Strategy Select should display Keyword + BFS as selected value
    // (appears at least once as SelectValue display)
    const matches = screen.getAllByText("Keyword + BFS（推薦）");
    expect(matches.length).toBeGreaterThanOrEqual(1);
  });

});
