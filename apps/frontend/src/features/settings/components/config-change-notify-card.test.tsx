/** Issue #77 — 租戶「設定變更通知」卡（hook 以 vi.mock 隔離） */

import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { ConfigChangeNotifyCard } from "@/features/settings/components/config-change-notify-card";
import { renderWithProviders } from "@/test/test-utils";
import type { TenantNotificationPreferences } from "@/types/notification-preferences";

vi.mock("@/hooks/queries/use-notification-preferences", () => ({
  useTenantNotificationPreferences: vi.fn(),
  useUpdateTenantNotificationPreferences: vi.fn(),
}));

import {
  useTenantNotificationPreferences,
  useUpdateTenantNotificationPreferences,
} from "@/hooks/queries/use-notification-preferences";

const prefsMock = vi.mocked(useTenantNotificationPreferences);
const updateMock = vi.mocked(useUpdateTenantNotificationPreferences);
const mutate = vi.fn();

const GROUPS: TenantNotificationPreferences["available_groups"] = [
  { key: "model", label: "模型" },
  { key: "prompt", label: "提示詞" },
  { key: "knowledge", label: "知識庫" },
  { key: "tools", label: "工具" },
  { key: "guard", label: "防護" },
];

function mockPrefs(
  data: TenantNotificationPreferences | undefined,
  extra: Record<string, unknown> = {},
) {
  prefsMock.mockReturnValue({
    data,
    isLoading: false,
    isError: false,
    ...extra,
  } as unknown as ReturnType<typeof useTenantNotificationPreferences>);
}

function checkbox(label: string) {
  return screen.getByRole("checkbox", { name: label });
}

describe("ConfigChangeNotifyCard", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    updateMock.mockReturnValue({
      mutate,
      isPending: false,
    } as unknown as ReturnType<typeof useUpdateTenantNotificationPreferences>);
  });

  it("prefills from effective_fields when the tenant has no override and marks it 平台預設", () => {
    mockPrefs({
      tenant_id: "t-1",
      config_change_notify_fields: null,
      effective_fields: ["model", "prompt"],
      available_groups: GROUPS,
    });
    renderWithProviders(<ConfigChangeNotifyCard tenantId="t-1" />);

    expect(prefsMock).toHaveBeenCalledWith("t-1");
    expect(screen.getByText("平台預設")).toBeInTheDocument();
    expect(screen.getByText(/系統管理員對本租戶的變更也會通知/)).toBeInTheDocument();
    expect(checkbox("模型")).toHaveAttribute("aria-checked", "true");
    expect(checkbox("提示詞")).toHaveAttribute("aria-checked", "true");
    expect(checkbox("知識庫")).toHaveAttribute("aria-checked", "false");
    expect(checkbox("工具")).toHaveAttribute("aria-checked", "false");
    expect(checkbox("防護")).toHaveAttribute("aria-checked", "false");
    // 已是平台預設 → 還原鈕停用；尚未變更 → 儲存鈕停用
    expect(screen.getByRole("button", { name: "還原平台預設" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "儲存" })).toBeDisabled();
  });

  it("prefills from the tenant override when present and marks it 租戶自訂", () => {
    mockPrefs({
      tenant_id: "t-1",
      config_change_notify_fields: ["guard"],
      effective_fields: ["guard"],
      available_groups: GROUPS,
    });
    renderWithProviders(<ConfigChangeNotifyCard tenantId="t-1" />);

    expect(screen.getByText("租戶自訂")).toBeInTheDocument();
    expect(checkbox("防護")).toHaveAttribute("aria-checked", "true");
    expect(checkbox("模型")).toHaveAttribute("aria-checked", "false");
    expect(screen.getByRole("button", { name: "還原平台預設" })).toBeEnabled();
  });

  it("saves the selected group keys as an array", async () => {
    const user = userEvent.setup();
    mockPrefs({
      tenant_id: "t-1",
      config_change_notify_fields: null,
      effective_fields: ["model"],
      available_groups: GROUPS,
    });
    renderWithProviders(<ConfigChangeNotifyCard tenantId="t-1" />);

    await user.click(checkbox("知識庫"));
    await user.click(checkbox("模型"));
    await user.click(screen.getByRole("button", { name: "儲存" }));

    expect(mutate).toHaveBeenCalledTimes(1);
    expect(mutate.mock.calls[0][0]).toEqual({ config_change_notify_fields: ["knowledge"] });
  });

  it("還原平台預設 sends null", async () => {
    const user = userEvent.setup();
    mockPrefs({
      tenant_id: "t-1",
      config_change_notify_fields: ["guard"],
      effective_fields: ["guard"],
      available_groups: GROUPS,
    });
    renderWithProviders(<ConfigChangeNotifyCard tenantId="t-1" />);

    await user.click(screen.getByRole("button", { name: "還原平台預設" }));
    expect(mutate.mock.calls[0][0]).toEqual({ config_change_notify_fields: null });
  });

  it("renders loading / error / no-tenant states", () => {
    mockPrefs(undefined, { isLoading: true });
    const { unmount } = renderWithProviders(<ConfigChangeNotifyCard tenantId="t-1" />);
    expect(screen.getByTestId("config-change-notify-loading")).toBeInTheDocument();
    unmount();

    mockPrefs(undefined, { isError: true });
    const r2 = renderWithProviders(<ConfigChangeNotifyCard tenantId="t-1" />);
    expect(screen.getByText("載入設定變更通知偏好失敗。")).toBeInTheDocument();
    r2.unmount();

    mockPrefs(undefined);
    renderWithProviders(<ConfigChangeNotifyCard tenantId={null} />);
    const card = screen.getByTestId("config-change-notify-card");
    expect(within(card).getByText("尚未綁定租戶")).toBeInTheDocument();
  });
});
