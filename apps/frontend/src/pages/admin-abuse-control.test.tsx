import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import AdminAbuseControlPage from "@/pages/admin-abuse-control";
import { renderWithProviders } from "@/test/test-utils";
import type { AbuseControlItem, AbuseSettingsOverview } from "@/types/abuse-control";

vi.mock("@/hooks/queries/use-abuse-control", () => ({
  useAbuseSettingsOverview: vi.fn(),
  useTenantAbuseSettings: vi.fn(() => ({ data: undefined, isLoading: false })),
  useUpdatePlatformAbuseSettings: vi.fn(),
  useUpdateAbuseProfile: vi.fn(() => ({ mutate: vi.fn(), isPending: false })),
  useUpdateTenantAbuseSettings: vi.fn(() => ({ mutate: vi.fn(), isPending: false })),
  useAbuseControls: vi.fn(),
  useReleaseAbuseControl: vi.fn(),
}));

vi.mock("@/hooks/queries/use-tenants", () => ({
  useTenants: vi.fn(() => ({
    data: { items: [{ id: "t-1", name: "家樂福" }], total: 1, page: 1, page_size: 100, total_pages: 1 },
  })),
}));

import {
  useAbuseControls,
  useAbuseSettingsOverview,
  useReleaseAbuseControl,
  useUpdatePlatformAbuseSettings,
} from "@/hooks/queries/use-abuse-control";

const overviewMock = vi.mocked(useAbuseSettingsOverview);
const platformMutationMock = vi.mocked(useUpdatePlatformAbuseSettings);
const controlsMock = vi.mocked(useAbuseControls);
const releaseMock = vi.mocked(useReleaseAbuseControl);

const platformMutate = vi.fn();
const releaseMutate = vi.fn();

const OVERVIEW: AbuseSettingsOverview = {
  platform_overrides: { mode: "enforce" },
  profiles: {
    standard: {},
    strict: { threshold_l1: 2, threshold_l2: 5, threshold_l3: 10, threshold_l4: 20 },
    monitor: { mode: "monitor" },
    vip: { pacing_max_per_minute: 60 },
  },
  effective_default: {
    mode: "enforce",
    enabled: true,
    threshold_l1: 3,
    threshold_l2: 8,
    threshold_l3: 15,
    threshold_l4: 30,
    duration_l2: 300,
    duration_l3: 900,
    duration_l4: 3600,
    decay_per_minute: 1,
    pacing_max_per_minute: 20,
    unrouted_free_count: 2,
    slow_requests_per_minute: 6,
    line_silent_on_cooldown: true,
    ip_layer_enabled: true,
    ip_allowlist: [],
    weight_guard_hit: 5,
    weight_attack: 5,
    weight_pacing: 3,
    weight_unrouted: 1,
    weight_origin_mismatch: 5,
    weight_identify_fail: 2,
    max_level_visitor: 4,
    max_level_end_user: 4,
    max_level_line_user: 4,
    max_level_user: 3,
    max_level_client: 4,
    max_level_ip: 4,
    max_level_tenant: 2,
  },
  allowed_keys: [
    "mode", "enabled", "threshold_l1", "threshold_l2", "threshold_l3", "threshold_l4",
    "duration_l2", "duration_l3", "duration_l4", "decay_per_minute",
    "pacing_max_per_minute", "unrouted_free_count", "slow_requests_per_minute",
    "line_silent_on_cooldown", "ip_layer_enabled", "ip_allowlist", "profile",
  ],
  bounds: {
    threshold_l1: [1, 50],
    threshold_l2: [2, 100],
    threshold_l3: [3, 200],
    threshold_l4: [4, 400],
    pacing_max_per_minute: [5, 120],
  },
};

const CONTROL: AbuseControlItem = {
  tenant_id: "t-1",
  subject_kind: "visitor",
  subject_id: "visitor-abc-123",
  subject_masked: "vis***123",
  level: 3,
  remaining_seconds: 245,
};

describe("AdminAbuseControlPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    overviewMock.mockReturnValue({
      data: OVERVIEW,
      isLoading: false,
      isError: false,
    } as unknown as ReturnType<typeof useAbuseSettingsOverview>);
    platformMutationMock.mockReturnValue({
      mutate: platformMutate,
      isPending: false,
    } as unknown as ReturnType<typeof useUpdatePlatformAbuseSettings>);
    controlsMock.mockReturnValue({
      data: [CONTROL],
      isLoading: false,
      isError: false,
      isFetching: false,
      dataUpdatedAt: 0,
      refetch: vi.fn(),
    } as unknown as ReturnType<typeof useAbuseControls>);
    releaseMock.mockReturnValue({
      mutate: releaseMutate,
      isPending: false,
    } as unknown as ReturnType<typeof useReleaseAbuseControl>);
  });

  it("系統預設：未變更時儲存按鈕停用", () => {
    renderWithProviders(<AdminAbuseControlPage />);
    expect(screen.getByRole("button", { name: "儲存系統預設" })).toBeDisabled();
    expect(screen.getByText("尚無變更")).toBeInTheDocument();
    // 生效值作為 placeholder
    expect(screen.getByLabelText("門檻 L1 觀察")).toHaveAttribute("placeholder", "3");
  });

  it("系統預設：只送出既有覆寫 + 使用者實際設定的鍵", async () => {
    const user = userEvent.setup();
    renderWithProviders(<AdminAbuseControlPage />);

    await user.type(screen.getByLabelText("門檻 L1 觀察"), "2");
    await user.type(screen.getByLabelText("每分鐘訊息上限"), "30");
    await user.click(screen.getByRole("button", { name: "儲存系統預設" }));

    expect(platformMutate).toHaveBeenCalledTimes(1);
    // 只有 mode（既有）+ 兩個新設定的鍵，其餘未觸碰的欄位不得混入 payload
    expect(platformMutate.mock.calls[0][0]).toEqual({
      mode: "enforce",
      threshold_l1: 2,
      pacing_max_per_minute: 30,
    });
  });

  it("系統預設：清空欄位即移除該鍵的覆寫", async () => {
    overviewMock.mockReturnValue({
      data: { ...OVERVIEW, platform_overrides: { mode: "enforce", threshold_l1: 2 } },
      isLoading: false,
      isError: false,
    } as unknown as ReturnType<typeof useAbuseSettingsOverview>);
    const user = userEvent.setup();
    renderWithProviders(<AdminAbuseControlPage />);

    const input = screen.getByLabelText("門檻 L1 觀察");
    expect(input).toHaveValue(2);
    await user.clear(input);
    await user.click(screen.getByRole("button", { name: "儲存系統預設" }));

    expect(platformMutate.mock.calls[0][0]).toEqual({ mode: "enforce" });
  });

  it("系統預設：門檻未遞增時擋下送出並顯示錯誤", async () => {
    const user = userEvent.setup();
    renderWithProviders(<AdminAbuseControlPage />);

    // effective threshold_l2 = 8，把 L1 設成 9 → 不遞增
    await user.type(screen.getByLabelText("門檻 L1 觀察"), "9");
    expect(screen.getByText("門檻必須遞增：L1 < L2 < L3 < L4")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "儲存系統預設" })).toBeDisabled();
    expect(platformMutate).not.toHaveBeenCalled();
  });

  it("方案：內建方案標示「內建」、自訂方案顯示覆寫項目", async () => {
    const user = userEvent.setup();
    renderWithProviders(<AdminAbuseControlPage />);
    await user.click(screen.getByRole("tab", { name: "方案" }));

    const strictRow = screen.getByRole("row", { name: /strict/ });
    expect(within(strictRow).getByText("內建")).toBeInTheDocument();
    const vipRow = screen.getByRole("row", { name: /vip/ });
    expect(within(vipRow).getByText("自訂")).toBeInTheDocument();
    expect(within(vipRow).getByText("每分鐘訊息上限：60")).toBeInTheDocument();
  });

  it("受控中：顯示等級與剩餘時間，解除需確認後才呼叫 API", async () => {
    const user = userEvent.setup();
    renderWithProviders(<AdminAbuseControlPage />);
    await user.click(screen.getByRole("tab", { name: "受控中" }));

    const row = screen.getByRole("row", { name: /vis\*\*\*123/ });
    expect(within(row).getByText("家樂福")).toBeInTheDocument();
    expect(within(row).getByText("訪客")).toBeInTheDocument();
    expect(within(row).getByText("L3 冷卻")).toBeInTheDocument();
    expect(within(row).getByText("04:05")).toBeInTheDocument();

    await user.click(within(row).getByRole("button", { name: "解除" }));
    const dialog = screen.getByRole("alertdialog");
    expect(releaseMutate).not.toHaveBeenCalled();

    await user.click(within(dialog).getByRole("button", { name: "取消" }));
    expect(releaseMutate).not.toHaveBeenCalled();

    await user.click(within(row).getByRole("button", { name: "解除" }));
    await user.click(
      within(screen.getByRole("alertdialog")).getByRole("button", { name: "確認解除" }),
    );

    expect(releaseMutate).toHaveBeenCalledTimes(1);
    expect(releaseMutate.mock.calls[0][0]).toEqual({
      tenant_id: "t-1",
      subject_kind: "visitor",
      subject_id: "visitor-abc-123",
    });
  });

  it("受控中：清單為空時顯示提示", async () => {
    controlsMock.mockReturnValue({
      data: [],
      isLoading: false,
      isError: false,
      isFetching: false,
      dataUpdatedAt: 0,
      refetch: vi.fn(),
    } as unknown as ReturnType<typeof useAbuseControls>);
    const user = userEvent.setup();
    renderWithProviders(<AdminAbuseControlPage />);
    await user.click(screen.getByRole("tab", { name: "受控中" }));
    expect(screen.getByText("目前沒有受控中的主體")).toBeInTheDocument();
  });
});
