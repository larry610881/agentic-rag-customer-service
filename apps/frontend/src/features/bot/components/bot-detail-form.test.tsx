import { describe, it, expect, vi, beforeEach } from "vitest";
import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { renderWithProviders } from "@/test/test-utils";
import { server } from "@/test/mocks/server";
import { BotDetailForm } from "@/features/bot/components/bot-detail-form";
import { mockBot } from "@/test/fixtures/bot";
import { useAuthStore } from "@/stores/use-auth-store";

function setTenantPermissions(overrides: {
  allowed_agent_modes?: string[];
}) {
  const tenant = {
    id: "tenant-1",
    name: "Test Tenant",
    plan: "pro",
    allowed_agent_modes: overrides.allowed_agent_modes ?? ["router", "react"],
    monthly_token_limit: null,
    created_at: "2024-01-01T00:00:00Z",
    updated_at: "2024-01-01T00:00:00Z",
  };
  // Use wildcard origin to match both relative URLs (jsdom: http://localhost)
  // and absolute URLs (MSW default: http://localhost:8000)
  server.use(
    http.get("*/api/v1/tenants", () => {
      return HttpResponse.json([tenant]);
    }),
  );
  useAuthStore.setState({
    token: "test-token",
    tenantId: "tenant-1",
    tenants: [tenant],
  });
}

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
          allowed_agent_modes: ["router", "react"],
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

  describe("tenant permission controls", () => {
    it("should show disabled text for react when allowed_agent_modes is ['router']", async () => {
      setTenantPermissions({ allowed_agent_modes: ["router"] });
      renderWithProviders(
        <BotDetailForm
          bot={mockBot}
          onSave={mockOnSave}
          onDelete={mockOnDelete}
          isSaving={false}
          isDeleting={false}
        />,
      );
      // Wait for tenant data to load and verify ReAct shows as disabled
      await waitFor(() => {
        expect(screen.getByText(/租戶未啟用/)).toBeInTheDocument();
      });
    });

    it("should not disable react option when allowed_agent_modes includes react", async () => {
      setTenantPermissions({ allowed_agent_modes: ["router", "react"] });
      renderWithProviders(
        <BotDetailForm
          bot={mockBot}
          onSave={mockOnSave}
          onDelete={mockOnDelete}
          isSaving={false}
          isDeleting={false}
        />,
      );
      // Wait for tenant data to load, then verify the visible disabled message
      // paragraph is absent (ignore Radix hidden native <option> elements)
      await waitFor(() => {
        const disabledParagraphs = screen.queryAllByText(/租戶未啟用/)
          .filter((el) => el.tagName !== "OPTION");
        expect(disabledParagraphs).toHaveLength(0);
      });
    });
  });
});
