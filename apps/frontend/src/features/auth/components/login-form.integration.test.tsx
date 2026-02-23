import { describe, it, expect, beforeEach } from "vitest";
import { screen, waitFor } from "@testing-library/react";
import { renderWithProviders, userEvent } from "@/test/test-utils";
import { LoginForm } from "@/features/auth/components/login-form";
import { useAuthStore } from "@/stores/use-auth-store";

describe("LoginForm integration", () => {
  beforeEach(() => {
    useAuthStore.setState({ token: null, tenantId: null, tenants: [] });
  });

  it("should login successfully and update auth store", async () => {
    const user = userEvent.setup();
    renderWithProviders(<LoginForm />);

    await user.type(screen.getByLabelText("Username"), "admin");
    await user.type(screen.getByLabelText("Password"), "password");
    await user.click(screen.getByRole("button", { name: "Sign in" }));

    await waitFor(() => {
      expect(useAuthStore.getState().token).toBe("mock-jwt-token-123");
    });
  });
});
