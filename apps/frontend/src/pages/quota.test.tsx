import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import QuotaPage from "@/pages/quota";
import { renderWithProviders } from "@/test/test-utils";
import { useAuthStore } from "@/stores/use-auth-store";
import type { TenantQuota } from "@/hooks/queries/use-tenant-quota";

vi.mock("@/hooks/queries/use-tenant-quota", () => ({
  useTenantQuota: vi.fn(),
}));

vi.mock("@/hooks/queries/use-tenant-billing-policy", () => ({
  useUpdateTenantBillingPolicy: vi.fn(),
}));

import { useTenantQuota } from "@/hooks/queries/use-tenant-quota";
import { useUpdateTenantBillingPolicy } from "@/hooks/queries/use-tenant-billing-policy";

const quotaMock = vi.mocked(useTenantQuota);
const policyMock = vi.mocked(useUpdateTenantBillingPolicy);
const policyMutateAsync = vi.fn();

const TOKEN_QUOTA: TenantQuota = {
  cycle_year_month: "2026-09",
  plan_name: "pro",
  base_total: 10_000_000,
  base_remaining: 4_000_000,
  addon_remaining: 0,
  total_remaining: 4_000_000,
  total_billable_in_cycle: 6_000_000,
  included_categories: null,
  billing_mode: "token",
  exhaustion_policy: "auto_topup",
  effective_policy: "auto_topup",
  tenant_may_change_policy: false,
  grace_percent: 0,
  block_message: "",
};

const POINTS_QUOTA: TenantQuota = {
  ...TOKEN_QUOTA,
  plan_name: "pro-points",
  billing_mode: "points",
  exhaustion_policy: "block",
  effective_policy: "block",
  tenant_may_change_policy: true,
  block_message: "額度用完",
  points_total: 5000,
  points_used: 1250,
  points_remaining: 3750,
};

function mockQuota(data: TenantQuota) {
  quotaMock.mockReturnValue({
    data,
    isLoading: false,
    isError: false,
  } as unknown as ReturnType<typeof useTenantQuota>);
}

describe("QuotaPage（Issue #74）", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    useAuthStore.setState({ token: "tok", tenantId: "tenant-1" });
    policyMutateAsync.mockResolvedValue({});
    policyMock.mockReturnValue({
      mutateAsync: policyMutateAsync,
      isPending: false,
    } as unknown as ReturnType<typeof useUpdateTenantBillingPolicy>);
  });

  it("Token 制：顯示 token 額度卡，無點數卡與「詳細 token」", () => {
    mockQuota(TOKEN_QUOTA);
    renderWithProviders(<QuotaPage />);

    expect(screen.getByText("本月已用")).toBeInTheDocument();
    expect(screen.getByText("Base 餘額（pro）")).toBeInTheDocument();
    expect(screen.queryByText("本月已用點數")).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /詳細 token/ })).not.toBeInTheDocument();
    expect(screen.getByText("Token 制")).toBeInTheDocument();
  });

  it("點數制：顯示點數已用 / 總額 / 剩餘，token 卡收進「詳細 token」可展開", async () => {
    mockQuota(POINTS_QUOTA);
    const user = userEvent.setup();
    renderWithProviders(<QuotaPage />);

    expect(screen.getByText("本月已用點數")).toBeInTheDocument();
    expect(screen.getByText("1,250")).toBeInTheDocument();
    expect(screen.getByText("3,750 / 5,000")).toBeInTheDocument();
    expect(screen.getByText("點數制")).toBeInTheDocument();
    expect(screen.queryByText("Base 餘額（pro-points）")).not.toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: /詳細 token/ }));
    expect(screen.getByText("Base 餘額（pro-points）")).toBeInTheDocument();
  });

  it("用盡策略：方案允許時可切換並儲存（送 exhaustion_policy + block_message）", async () => {
    mockQuota(POINTS_QUOTA);
    const user = userEvent.setup();
    renderWithProviders(<QuotaPage />);

    expect(screen.getByText("用完即擋")).toBeInTheDocument();
    const toggle = screen.getByRole("switch", { name: "自動展延" });
    expect(toggle).toBeEnabled();
    expect(toggle).not.toBeChecked();
    expect(screen.getByRole("button", { name: "儲存策略" })).toBeDisabled();

    await user.click(toggle);
    await user.click(screen.getByRole("button", { name: "儲存策略" }));

    await waitFor(() => expect(policyMutateAsync).toHaveBeenCalledTimes(1));
    expect(policyMutateAsync.mock.calls[0][0]).toEqual({
      exhaustion_policy: "auto_topup",
      block_message: "額度用完",
    });
  });

  it("用盡策略：徽章 / 開關以 effective_policy 為準；切回方案預設時送 null 清除覆寫", async () => {
    // 方案預設自動展延，租戶覆寫為用完即擋
    mockQuota({
      ...POINTS_QUOTA,
      exhaustion_policy: "auto_topup",
      effective_policy: "block",
      block_message: "",
    });
    const user = userEvent.setup();
    renderWithProviders(<QuotaPage />);

    expect(screen.getByText("用完即擋")).toBeInTheDocument();
    expect(screen.getByText(/方案預設：自動展延/)).toBeInTheDocument();
    const toggle = screen.getByRole("switch", { name: "自動展延" });
    expect(toggle).not.toBeChecked();

    await user.click(toggle);
    await user.click(screen.getByRole("button", { name: "儲存策略" }));

    await waitFor(() => expect(policyMutateAsync).toHaveBeenCalledTimes(1));
    expect(policyMutateAsync.mock.calls[0][0]).toEqual({
      exhaustion_policy: null,
      block_message: null,
    });
  });

  it("用盡策略：方案不允許時唯讀並提示「由方案決定」", () => {
    mockQuota(TOKEN_QUOTA);
    renderWithProviders(<QuotaPage />);

    const toggle = screen.getByRole("switch", { name: "自動展延" });
    expect(toggle).toBeDisabled();
    expect(toggle).toBeChecked();
    expect(screen.getByText(/由方案決定/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "儲存策略" })).not.toBeInTheDocument();
  });

  it("無 billing_mode 欄位（後端尚未升級）時視為 Token 制", () => {
    const legacy = { ...TOKEN_QUOTA };
    delete legacy.billing_mode;
    delete legacy.exhaustion_policy;
    delete legacy.effective_policy;
    delete legacy.tenant_may_change_policy;
    mockQuota(legacy);
    renderWithProviders(<QuotaPage />);

    expect(screen.getByText("本月已用")).toBeInTheDocument();
    expect(screen.getByText("Token 制")).toBeInTheDocument();
    expect(screen.getByRole("switch", { name: "自動展延" })).toBeDisabled();
  });
});
