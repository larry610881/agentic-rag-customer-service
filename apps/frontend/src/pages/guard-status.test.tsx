import { screen, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import GuardStatusPage from "@/pages/guard-status";
import { renderWithProviders } from "@/test/test-utils";
import { useAuthStore } from "@/stores/use-auth-store";
import type { TenantGuardSettings } from "@/types/guard-stages";

vi.mock("@/hooks/queries/use-guard-stages", () => ({
  useTenantGuardSettings: vi.fn(),
}));

import { useTenantGuardSettings } from "@/hooks/queries/use-guard-stages";

const settingsMock = vi.mocked(useTenantGuardSettings);

const SETTINGS: TenantGuardSettings = {
  tenant_id: "t-1",
  profile: "exhibition",
  overrides: { profile: "exhibition", stages: ["classifier_attack"] },
  locked: false,
  effective: {
    stages: ["regex_input", "classifier_attack", "output_guard"],
    required: ["regex_input"],
    locked: false,
    source_map: {
      regex_input: "required",
      classifier_attack: "tenant",
      output_guard: "profile",
    },
    profile: "exhibition",
  },
  editable: false,
};

function mockSettings(data: TenantGuardSettings | undefined, extra: Record<string, unknown> = {}) {
  settingsMock.mockReturnValue({
    data,
    isLoading: false,
    isError: false,
    ...extra,
  } as unknown as ReturnType<typeof useTenantGuardSettings>);
}

describe("GuardStatusPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    useAuthStore.setState({ token: "tok", tenantId: "t-1", role: "tenant_admin" });
    mockSettings(SETTINGS);
  });

  it("以自己的租戶 id 讀取，列出各階段狀態、來源與方案", () => {
    renderWithProviders(<GuardStatusPage />);

    expect(settingsMock).toHaveBeenCalledWith("t-1");
    expect(screen.getByText("方案：exhibition")).toBeInTheDocument();

    const regexRow = screen.getByTestId("guard-status-regex_input").closest("tr")!;
    expect(within(regexRow).getByText("啟用")).toBeInTheDocument();
    expect(within(regexRow).getByText("底線")).toBeInTheDocument();

    const classifierRow = screen.getByTestId("guard-status-classifier_attack").closest("tr")!;
    expect(within(classifierRow).getByText("租戶啟用")).toBeInTheDocument();

    const outputRow = screen.getByTestId("guard-status-output_guard").closest("tr")!;
    expect(within(outputRow).getByText("方案")).toBeInTheDocument();

    const abuseRow = screen.getByTestId("guard-status-abuse_scoring").closest("tr")!;
    expect(within(abuseRow).getByText("未啟用")).toBeInTheDocument();

    const localRow = screen.getByTestId("guard-status-local_classifier").closest("tr")!;
    expect(within(localRow).getByText("即將推出")).toBeInTheDocument();

    expect(screen.queryByText(/由系統管理員設定/)).not.toBeInTheDocument();
  });

  it("鎖定時顯示「由系統管理員設定」", () => {
    mockSettings({ ...SETTINGS, locked: true, effective: { ...SETTINGS.effective, locked: true } });
    renderWithProviders(<GuardStatusPage />);
    expect(screen.getByText(/由系統管理員設定/)).toBeInTheDocument();
  });

  it("沒有 tenantId 時顯示無法辨識租戶", () => {
    useAuthStore.setState({ tenantId: null });
    mockSettings(undefined);
    renderWithProviders(<GuardStatusPage />);
    expect(screen.getByText("無法辨識目前租戶")).toBeInTheDocument();
  });

  it("載入失敗時顯示錯誤", () => {
    mockSettings(undefined, { isError: true });
    renderWithProviders(<GuardStatusPage />);
    expect(screen.getByText("無法載入設定")).toBeInTheDocument();
  });
});
