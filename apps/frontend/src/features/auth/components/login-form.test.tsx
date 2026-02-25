import { describe, it, expect, beforeEach, vi } from "vitest";
import { screen, waitFor } from "@testing-library/react";
import { renderWithProviders, userEvent } from "@/test/test-utils";
import { LoginForm } from "@/features/auth/components/login-form";
import { useAuthStore } from "@/stores/use-auth-store";

const mockReplace = vi.fn();
vi.mock("next/navigation", () => ({
  useRouter: () => ({
    push: vi.fn(),
    replace: mockReplace,
    back: vi.fn(),
    forward: vi.fn(),
    refresh: vi.fn(),
    prefetch: vi.fn(),
  }),
  usePathname: () => "/login",
  useSearchParams: () => new URLSearchParams(),
}));

describe("LoginForm", () => {
  beforeEach(() => {
    useAuthStore.setState({ token: null, tenantId: null, tenants: [] });
  });

  it("should render login form fields", () => {
    renderWithProviders(<LoginForm />);
    expect(screen.getByLabelText("使用者名稱")).toBeInTheDocument();
    expect(screen.getByLabelText("密碼")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "登入" })).toBeInTheDocument();
  });

  it("should show validation errors when fields are empty", async () => {
    const user = userEvent.setup();
    renderWithProviders(<LoginForm />);
    await user.click(screen.getByRole("button", { name: "登入" }));
    expect(await screen.findByText("請輸入使用者名稱")).toBeInTheDocument();
    expect(await screen.findByText("請輸入密碼")).toBeInTheDocument();
  });

  it("should submit form with valid data and set token", async () => {
    const user = userEvent.setup();
    renderWithProviders(<LoginForm />);
    await user.type(screen.getByLabelText("使用者名稱"), "admin");
    await user.type(screen.getByLabelText("密碼"), "password");
    await user.click(screen.getByRole("button", { name: "登入" }));

    // After successful login, auth store should have the token
    await waitFor(() => {
      expect(useAuthStore.getState().token).toBe("mock-jwt-token-123");
    });
  });
});
