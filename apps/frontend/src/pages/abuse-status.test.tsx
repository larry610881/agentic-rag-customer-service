import { screen, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import AbuseStatusPage from "@/pages/abuse-status";
import { renderWithProviders } from "@/test/test-utils";
import { useAuthStore } from "@/stores/use-auth-store";
import type { AbuseControlItem, TenantAbuseSettings } from "@/types/abuse-control";

vi.mock("@/hooks/queries/use-abuse-control", () => ({
  useTenantAbuseSettings: vi.fn(),
  useAbuseControls: vi.fn(),
}));

import { useAbuseControls, useTenantAbuseSettings } from "@/hooks/queries/use-abuse-control";

const settingsMock = vi.mocked(useTenantAbuseSettings);
const controlsMock = vi.mocked(useAbuseControls);

const SETTINGS: TenantAbuseSettings = {
  tenant_id: "t-1",
  profile: "strict",
  overrides: { pacing_max_per_minute: 15 },
  effective: {
    mode: "enforce",
    enabled: true,
    threshold_l1: 2,
    threshold_l2: 5,
    threshold_l3: 10,
    threshold_l4: 20,
    pacing_max_per_minute: 15,
    line_silent_on_cooldown: false,
    ip_allowlist: ["10.0.0.0/8"],
    max_level_visitor: 4,
  },
  editable: false,
};

const CONTROL: AbuseControlItem = {
  tenant_id: "t-1",
  subject_kind: "line_user",
  subject_id: null,
  subject_masked: "U12***9f",
  level: 4,
  remaining_seconds: 3725,
};

describe("AbuseStatusPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    useAuthStore.setState({ token: "tok", tenantId: "t-1", role: "tenant_admin" });
    settingsMock.mockReturnValue({
      data: SETTINGS,
      isLoading: false,
      isError: false,
    } as unknown as ReturnType<typeof useTenantAbuseSettings>);
    controlsMock.mockReturnValue({
      data: [CONTROL],
      isLoading: false,
      isError: false,
      isFetching: false,
      dataUpdatedAt: 0,
      refetch: vi.fn(),
    } as unknown as ReturnType<typeof useAbuseControls>);
  });

  it("以自己的租戶 id 讀取設定，並顯示生效值與方案", () => {
    renderWithProviders(<AbuseStatusPage />);

    expect(settingsMock).toHaveBeenCalledWith("t-1");
    expect(controlsMock).toHaveBeenCalledWith("t-1");
    expect(screen.getByText("由系統管理員設定")).toBeInTheDocument();
    expect(screen.getByText("方案：strict（嚴格）")).toBeInTheDocument();

    expect(screen.getByTestId("effective-mode")).toHaveTextContent("執行");
    expect(screen.getByTestId("effective-threshold_l1")).toHaveTextContent("2");
    expect(screen.getByTestId("effective-pacing_max_per_minute")).toHaveTextContent("15");
    expect(screen.getByTestId("effective-line_silent_on_cooldown")).toHaveTextContent("否");
    expect(screen.getByTestId("effective-ip_allowlist")).toHaveTextContent("10.0.0.0/8");
    expect(screen.getByTestId("effective-max_level_visitor")).toHaveTextContent("4（封鎖）");

    // 租戶覆寫的鍵標示來源
    const pacingRow = screen.getByTestId("effective-pacing_max_per_minute").closest("tr")!;
    expect(within(pacingRow).getByText("租戶覆寫")).toBeInTheDocument();
  });

  it("受控清單只顯示遮罩主體，且沒有解除按鈕", () => {
    renderWithProviders(<AbuseStatusPage />);

    const row = screen.getByRole("row", { name: /U12\*\*\*9f/ });
    expect(within(row).getByText("LINE 使用者")).toBeInTheDocument();
    expect(within(row).getByText("L4 封鎖")).toBeInTheDocument();
    expect(within(row).getByText("1:02:05")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "解除" })).not.toBeInTheDocument();
  });

  it("沒有 tenantId 時顯示無法辨識租戶", () => {
    useAuthStore.setState({ tenantId: null });
    settingsMock.mockReturnValue({
      data: undefined,
      isLoading: false,
      isError: false,
    } as unknown as ReturnType<typeof useTenantAbuseSettings>);
    renderWithProviders(<AbuseStatusPage />);
    expect(screen.getByText("無法辨識目前租戶")).toBeInTheDocument();
  });
});
