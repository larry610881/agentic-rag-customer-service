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
      screen.getByRole("button", { name: "Create Bot" }),
    ).toBeInTheDocument();
  });

  it("should open dialog on button click", async () => {
    const user = userEvent.setup();
    renderWithProviders(<CreateBotDialog />);
    await user.click(screen.getByRole("button", { name: "Create Bot" }));
    expect(screen.getByText("Create a new bot to handle customer conversations.")).toBeInTheDocument();
  });

  it("should show validation error for empty name", async () => {
    const user = userEvent.setup();
    renderWithProviders(<CreateBotDialog />);
    await user.click(screen.getByRole("button", { name: "Create Bot" }));
    // Submit without entering name
    await user.click(screen.getByRole("button", { name: "Create" }));
    await waitFor(() => {
      expect(screen.getByText("Name is required")).toBeInTheDocument();
    });
  });
});
