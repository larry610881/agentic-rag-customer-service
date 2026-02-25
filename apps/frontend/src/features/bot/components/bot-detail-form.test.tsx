import { describe, it, expect, vi, beforeEach } from "vitest";
import { screen } from "@testing-library/react";
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
      tenants: [],
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

  it("should render LLM parameter inputs", () => {
    renderWithProviders(
      <BotDetailForm
        bot={mockBot}
        onSave={mockOnSave}
        onDelete={mockOnDelete}
        isSaving={false}
        isDeleting={false}
      />,
    );
    expect(screen.getByLabelText("溫度（0-1）")).toHaveValue(0.3);
    expect(screen.getByLabelText("最大 Token 數（128-4096）")).toHaveValue(1024);
    expect(screen.getByLabelText("歷史訊息數（0-35）")).toHaveValue(10);
  });

  it("should render system prompt textarea", () => {
    renderWithProviders(
      <BotDetailForm
        bot={mockBot}
        onSave={mockOnSave}
        onDelete={mockOnDelete}
        isSaving={false}
        isDeleting={false}
      />,
    );
    expect(screen.getByLabelText("自訂系統提示詞")).toHaveValue(
      "You are a helpful customer service bot.",
    );
  });

  it("should render LINE channel fields", () => {
    renderWithProviders(
      <BotDetailForm
        bot={mockBot}
        onSave={mockOnSave}
        onDelete={mockOnDelete}
        isSaving={false}
        isDeleting={false}
      />,
    );
    expect(screen.getByLabelText("頻道密鑰")).toBeInTheDocument();
    expect(screen.getByLabelText("存取權杖")).toBeInTheDocument();
  });

  it("should render enabled tools checkboxes", () => {
    renderWithProviders(
      <BotDetailForm
        bot={mockBot}
        onSave={mockOnSave}
        onDelete={mockOnDelete}
        isSaving={false}
        isDeleting={false}
      />,
    );
    expect(screen.getByLabelText("知識庫查詢")).toBeChecked();
    expect(screen.getByLabelText("訂單查詢")).toBeChecked();
    expect(screen.getByLabelText("商品搜尋")).not.toBeChecked();
    expect(screen.getByLabelText("建立工單")).not.toBeChecked();
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
});
