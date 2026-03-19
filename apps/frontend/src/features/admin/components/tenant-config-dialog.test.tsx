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
  allowed_agent_modes: ["router", "react"],
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
    // Ensure PATCH endpoints match relative URLs (API_BASE="" in test env)
    server.use(
      http.patch("*/api/v1/tenants/:tenantId/config", async ({ request }) => {
        const body = (await request.json()) as { monthly_token_limit: number | null };
        return HttpResponse.json({
          ...mockTenant,
          monthly_token_limit: body.monthly_token_limit,
          updated_at: new Date().toISOString(),
        });
      }),
      http.patch("*/api/v1/tenants/:tenantId/agent-modes", async ({ request }) => {
        const body = (await request.json()) as { allowed_agent_modes: string[] };
        return HttpResponse.json({
          ...mockTenant,
          allowed_agent_modes: body.allowed_agent_modes,
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

  it("should render Router switch as disabled", () => {
    renderWithProviders(
      <TenantConfigDialog
        tenant={mockTenant}
        open={true}
        onOpenChange={mockOnOpenChange}
      />,
    );
    const routerSwitch = document.getElementById("agent-mode-router") as HTMLButtonElement;
    expect(routerSwitch).toBeTruthy();
    expect(routerSwitch.getAttribute("data-disabled")).toBe("");
    expect(routerSwitch).toHaveAttribute("disabled");
    expect(screen.getByText("Router（預設）")).toBeInTheDocument();
  });

  it("should render ReAct switch that can be toggled on", async () => {
    const user = userEvent.setup();
    renderWithProviders(
      <TenantConfigDialog
        tenant={mockTenant}
        open={true}
        onOpenChange={mockOnOpenChange}
      />,
    );
    const reactSwitch = document.getElementById("agent-mode-react") as HTMLButtonElement;
    expect(reactSwitch).toBeTruthy();
    // Dialog opens with agentModes=[] (handleOpen not called on mount),
    // so ReAct starts unchecked
    expect(reactSwitch.getAttribute("data-state")).toBe("unchecked");
    expect(reactSwitch.getAttribute("data-disabled")).toBeNull();
    expect(screen.getByText("ReAct")).toBeInTheDocument();
    // Click to enable
    await user.click(reactSwitch);
    await waitFor(() => {
      expect(reactSwitch.getAttribute("data-state")).toBe("checked");
    });
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
