import { describe, it, expect, beforeEach } from "vitest";
import { screen } from "@testing-library/react";

import { renderWithProviders } from "@/test/test-utils";
import { AdminEmptyStateHint } from "@/components/shared/admin-empty-state-hint";
import { useAuthStore } from "@/stores/use-auth-store";

describe("AdminEmptyStateHint", () => {
  beforeEach(() => {
    useAuthStore.setState({
      token: "t",
      tenantId: "00000000-0000-0000-0000-000000000000",
      role: null,
      tenants: [],
    });
  });

  it("happy: admin + isEmpty → 顯示指引與連結", () => {
    useAuthStore.setState({ role: "system_admin" });

    renderWithProviders(
      <AdminEmptyStateHint resource="bots" isEmpty />,
    );

    expect(screen.getByRole("status")).toBeInTheDocument();
    expect(screen.getAllByText(/系統租戶/).length).toBeGreaterThan(0);
    const link = screen.getByRole("link", {
      name: /前往系統管理.*所有機器人/,
    });
    expect(link).toHaveAttribute("href", "/admin/bots");
  });

  it("admin + 有資料（isEmpty=false）→ 不顯示", () => {
    useAuthStore.setState({ role: "system_admin" });

    const { container } = renderWithProviders(
      <AdminEmptyStateHint resource="bots" isEmpty={false} />,
    );

    expect(container.firstChild).toBeNull();
  });

  it("非 admin + isEmpty → 不顯示（該頁自己的 EmptyState 接手）", () => {
    useAuthStore.setState({ role: "tenant_admin" });

    const { container } = renderWithProviders(
      <AdminEmptyStateHint resource="bots" isEmpty />,
    );

    expect(container.firstChild).toBeNull();
  });

  it("resource 不同會顯示不同 CTA 與 link", () => {
    useAuthStore.setState({ role: "system_admin" });

    renderWithProviders(
      <AdminEmptyStateHint resource="knowledge-bases" isEmpty />,
    );

    const link = screen.getByRole("link", {
      name: /前往系統管理.*所有知識庫/,
    });
    expect(link).toHaveAttribute("href", "/admin/knowledge-bases");
  });
});
