import { describe, it, expect, beforeEach } from "vitest";
import { screen, waitFor } from "@testing-library/react";
import { renderWithProviders, userEvent } from "@/test/test-utils";
import { CreateBotDialog } from "@/features/bot/components/create-bot-dialog";
import { useAuthStore } from "@/stores/use-auth-store";

describe("CreateBotDialog", () => {
  beforeEach(() => {
    useAuthStore.setState({
      token: "test-token",
      tenantId: "tenant-1",
      tenants: [],
    });
  });

  it("should render create button", () => {
    renderWithProviders(<CreateBotDialog />);
    expect(
      screen.getByRole("button", { name: "建立機器人" }),
    ).toBeInTheDocument();
  });

  it("should open dialog on button click", async () => {
    const user = userEvent.setup();
    renderWithProviders(<CreateBotDialog />);
    await user.click(screen.getByRole("button", { name: "建立機器人" }));
    expect(screen.getByText("建立新的機器人來處理客戶對話。")).toBeInTheDocument();
  });

  it("should show validation error for empty name", async () => {
    const user = userEvent.setup();
    renderWithProviders(<CreateBotDialog />);
    await user.click(screen.getByRole("button", { name: "建立機器人" }));
    // 未輸入名稱直接送出
    await user.click(screen.getByRole("button", { name: "建立" }));
    await waitFor(() => {
      expect(screen.getByText("請輸入名稱")).toBeInTheDocument();
    });
  });
});
