import { describe, it, expect, vi, beforeEach } from "vitest";
import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { renderWithProviders } from "@/test/test-utils";
import { server } from "@/test/mocks/server";
import { TenantConfigDialog } from "@/features/admin/components/tenant-config-dialog";
import { useAuthStore } from "@/stores/use-auth-store";
import type { Tenant } from "@/types/auth";

const mockTenant: Tenant = {
  id: "tenant-1",
  name: "Acme Corp",
  plan: "pro",
  monthly_token_limit: null,
  created_at: "2024-01-01T00:00:00Z",
  updated_at: "2024-01-01T00:00:00Z",
};

describe("TenantConfigDialog", () => {
  const mockOnOpenChange = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
    useAuthStore.setState({
      token: "test-token",
      tenantId: "tenant-1",
      tenants: [mockTenant],
    });
    server.use(
      http.patch("*/api/v1/tenants/:tenantId/config", async ({ request }) => {
        const body = (await request.json()) as { monthly_token_limit: number | null };
        return HttpResponse.json({
          ...mockTenant,
          monthly_token_limit: body.monthly_token_limit,
          updated_at: new Date().toISOString(),
        });
      }),
    );
  });

  it("should display tenant name in dialog title", () => {
    renderWithProviders(
      <TenantConfigDialog
        tenant={mockTenant}
        open={true}
        onOpenChange={mockOnOpenChange}
      />,
    );
    expect(screen.getByText("租戶設定 — Acme Corp")).toBeInTheDocument();
  });

  it("should allow entering monthly token limit and saving", async () => {
    const user = userEvent.setup();
    renderWithProviders(
      <TenantConfigDialog
        tenant={mockTenant}
        open={true}
        onOpenChange={mockOnOpenChange}
      />,
    );
    const limitInput = screen.getByLabelText("每月 Token 上限");
    await user.type(limitInput, "500000");
    expect(limitInput).toHaveValue(500000);
    const saveButton = screen.getByRole("button", { name: "儲存" });
    await user.click(saveButton);
    await waitFor(() => {
      expect(mockOnOpenChange).toHaveBeenCalledWith(false);
    });
  });
});
