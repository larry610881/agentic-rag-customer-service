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

/** Stage 4.5: 捕捉 PATCH body 讓多個 it() 共用 */
function registerPatchSpy(): { lastBody: Record<string, unknown> | null } {
  const spy: { lastBody: Record<string, unknown> | null } = { lastBody: null };
  server.use(
    http.patch("*/api/v1/tenants/:tenantId/config", async ({ request }) => {
      const body = (await request.json()) as Record<string, unknown>;
      spy.lastBody = body;
      return HttpResponse.json({
        ...mockTenant,
        ...body,
        updated_at: new Date().toISOString(),
      });
    }),
  );
  return spy;
}

describe("TenantConfigDialog", () => {
  const mockOnOpenChange = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
    useAuthStore.setState({
      token: "test-token",
      tenantId: "tenant-1",
      tenants: [mockTenant],
    });
  });

  it("should display tenant name in dialog title", () => {
    registerPatchSpy();
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
    registerPatchSpy();
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

  // ---- Bug 1 修復 Stage 4.5 新增 ----

  it("未打開進階 → PATCH body 不含 included_categories key", async () => {
    const spy = registerPatchSpy();
    const user = userEvent.setup();
    renderWithProviders(
      <TenantConfigDialog
        tenant={mockTenant}
        open={true}
        onOpenChange={mockOnOpenChange}
      />,
    );
    // 直接按儲存（不觸碰進階）
    await user.click(screen.getByRole("button", { name: "儲存" }));
    await waitFor(() => expect(spy.lastBody).not.toBeNull());

    expect(spy.lastBody).not.toHaveProperty("included_categories");
  });

  it("打開進階 + 啟用自訂 + 勾部分 category → PATCH body 帶 list", async () => {
    const spy = registerPatchSpy();
    const user = userEvent.setup();
    renderWithProviders(
      <TenantConfigDialog
        tenant={mockTenant}
        open={true}
        onOpenChange={mockOnOpenChange}
      />,
    );

    // 展開「進階」
    await user.click(
      screen.getByRole("button", { name: /進階：自訂計費 category/ }),
    );

    // 啟用「啟用自訂模式」
    const enableToggle = screen.getByLabelText(
      /啟用自訂模式（不啟用 = 全部 category 都計入額度）/,
    );
    await user.click(enableToggle);

    // 取消勾掉 LINE 對話（預設全勾 12 個，取消 1 個變 11 個）
    const lineCheckbox = screen.getByLabelText("LINE 對話");
    await user.click(lineCheckbox);

    await user.click(screen.getByRole("button", { name: "儲存" }));
    await waitFor(() => expect(spy.lastBody).not.toBeNull());

    const sent = spy.lastBody!.included_categories as string[];
    expect(Array.isArray(sent)).toBe(true);
    expect(sent).not.toContain("chat_line");
    expect(sent).toContain("rag"); // 其他未動的仍在
    expect(sent).toHaveLength(11);
  });

  it("打開進階 + 取消啟用自訂 → PATCH body.included_categories 為 null（Bug 1 修復）", async () => {
    const spy = registerPatchSpy();
    const user = userEvent.setup();
    // 租戶當前有 included_categories，Dialog 開啟時 toggle 會預設為 enabled
    const tenantWithCats: Tenant = {
      ...mockTenant,
      included_categories: ["rag", "chat_web"],
    };
    renderWithProviders(
      <TenantConfigDialog
        tenant={tenantWithCats}
        open={true}
        onOpenChange={mockOnOpenChange}
      />,
    );

    // 展開進階
    await user.click(
      screen.getByRole("button", { name: /進階：自訂計費 category/ }),
    );

    // 取消「啟用自訂模式」checkbox（已預設 enabled，因為 tenant 有 included_categories）
    const enableToggle = screen.getByLabelText(
      /啟用自訂模式（不啟用 = 全部 category 都計入額度）/,
    );
    await user.click(enableToggle);

    await user.click(screen.getByRole("button", { name: "儲存" }));
    await waitFor(() => expect(spy.lastBody).not.toBeNull());

    expect(spy.lastBody).toHaveProperty("included_categories");
    expect(spy.lastBody!.included_categories).toBeNull();
  });

  it("「其他」不應出現在 category checkbox（OTHER enum 已刪）", async () => {
    registerPatchSpy();
    const user = userEvent.setup();
    renderWithProviders(
      <TenantConfigDialog
        tenant={mockTenant}
        open={true}
        onOpenChange={mockOnOpenChange}
      />,
    );
    await user.click(
      screen.getByRole("button", { name: /進階：自訂計費 category/ }),
    );
    const enableToggle = screen.getByLabelText(
      /啟用自訂模式（不啟用 = 全部 category 都計入額度）/,
    );
    await user.click(enableToggle);

    expect(screen.queryByLabelText("其他")).not.toBeInTheDocument();
  });
});
