import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import AdminNotificationChannelsPage from "@/pages/admin-notification-channels";
import { renderWithProviders } from "@/test/test-utils";
import type { NotificationChannel } from "@/types/error-event";

vi.mock("@/hooks/queries/use-notification-channels", () => ({
  useNotificationChannels: vi.fn(),
  useCreateChannel: vi.fn(),
  useUpdateChannel: vi.fn(),
  useDeleteChannel: vi.fn(() => ({ mutate: vi.fn(), isPending: false })),
  useTestChannel: vi.fn(() => ({ mutate: vi.fn(), isPending: false })),
}));

import {
  useNotificationChannels,
  useCreateChannel,
  useUpdateChannel,
} from "@/hooks/queries/use-notification-channels";

const useChannelsMock = vi.mocked(useNotificationChannels);
const useCreateMock = vi.mocked(useCreateChannel);
const useUpdateMock = vi.mocked(useUpdateChannel);

const createMutate = vi.fn();
const updateMutate = vi.fn();

const TEAMS_CHANNEL: NotificationChannel = {
  id: "ch-teams",
  channel_type: "teams",
  name: "Teams 營運群",
  enabled: true,
  config: { webhook_url: "https://prod-1.logic.azure.com/workflows/abc" },
  throttle_minutes: 5,
  min_severity: "all",
  notify_diagnostics: false,
  diagnostic_severity: "critical",
  notify_abuse: false,
  updated_at: "2026-09-01T08:00:00Z",
  created_at: "2026-09-01T08:00:00Z",
};

const EMAIL_INCOMPLETE: NotificationChannel = {
  id: "ch-email",
  channel_type: "email",
  name: "值班信箱",
  enabled: true,
  config: { smtp_host: "smtp.example.com", recipients: [] },
  throttle_minutes: 10,
  min_severity: "5xx_only",
  notify_diagnostics: true,
  diagnostic_severity: "warning",
  notify_abuse: true,
  updated_at: "2026-09-01T08:00:00Z",
  created_at: "2026-09-01T08:00:00Z",
};

function setChannels(items: NotificationChannel[]) {
  useChannelsMock.mockReturnValue({
    data: items,
    isLoading: false,
  } as unknown as ReturnType<typeof useNotificationChannels>);
}

describe("AdminNotificationChannelsPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    useCreateMock.mockReturnValue({
      mutate: createMutate,
      isPending: false,
    } as unknown as ReturnType<typeof useCreateChannel>);
    useUpdateMock.mockReturnValue({
      mutate: updateMutate,
      isPending: false,
    } as unknown as ReturnType<typeof useUpdateChannel>);
    setChannels([]);
  });

  it("新增渠道：異常控管告警預設開啟且包含在建立 payload", async () => {
    const user = userEvent.setup();
    renderWithProviders(<AdminNotificationChannelsPage />);

    await user.click(screen.getByRole("button", { name: "新增渠道" }));
    const dialog = screen.getByRole("dialog");

    const abuseSwitch = within(dialog).getByRole("switch", {
      name: "異常控管告警",
    });
    expect(abuseSwitch).toHaveAttribute("aria-checked", "true");
    expect(
      within(dialog).getByText(
        "L3/L4 冷卻與封鎖、控管失效（fail-open）、429 突增、每日摘要",
      ),
    ).toBeInTheDocument();

    await user.type(within(dialog).getByPlaceholderText("例：Slack #alerts"), "Slack #alerts");
    await user.type(
      within(dialog).getByPlaceholderText("https://hooks.slack.com/services/..."),
      "https://hooks.slack.com/services/T/B/x",
    );
    await user.click(within(dialog).getByRole("button", { name: "建立" }));

    expect(createMutate).toHaveBeenCalledTimes(1);
    expect(createMutate.mock.calls[0][0]).toMatchObject({
      channel_type: "slack",
      name: "Slack #alerts",
      notify_abuse: true,
      config: { webhook_url: "https://hooks.slack.com/services/T/B/x" },
    });
  });

  it("新增渠道：關閉異常控管告警後 payload 為 false", async () => {
    const user = userEvent.setup();
    renderWithProviders(<AdminNotificationChannelsPage />);

    await user.click(screen.getByRole("button", { name: "新增渠道" }));
    const dialog = screen.getByRole("dialog");
    await user.click(within(dialog).getByRole("switch", { name: "異常控管告警" }));
    await user.type(within(dialog).getByPlaceholderText("例：Slack #alerts"), "x");
    await user.click(within(dialog).getByRole("button", { name: "建立" }));

    expect(createMutate.mock.calls[0][0]).toMatchObject({ notify_abuse: false });
  });

  it("編輯 Teams 渠道：顯示 Workflows 說明並回填 notify_abuse 到更新 payload", async () => {
    const user = userEvent.setup();
    setChannels([TEAMS_CHANNEL]);
    renderWithProviders(<AdminNotificationChannelsPage />);

    const row = screen.getByRole("row", { name: /Teams 營運群/ });
    // 操作欄第一顆是編輯（icon-only，無可存取名稱）
    await user.click(within(row).getAllByRole("button")[0]);
    const dialog = screen.getByRole("dialog");

    expect(
      within(dialog).getByText(
        "請使用 Teams Workflows（Power Automate）「When a Teams webhook request is received」產生的 URL；舊版 Office 365 Connector Incoming Webhook 已退場。",
      ),
    ).toBeInTheDocument();

    // 既有值 false 應被回填
    const abuseSwitch = within(dialog).getByRole("switch", { name: "異常控管告警" });
    expect(abuseSwitch).toHaveAttribute("aria-checked", "false");

    await user.click(abuseSwitch);
    await user.click(within(dialog).getByRole("button", { name: "更新" }));

    expect(updateMutate).toHaveBeenCalledTimes(1);
    expect(updateMutate.mock.calls[0][0]).toMatchObject({
      id: "ch-teams",
      data: { notify_abuse: true },
    });
  });

  it("列表：email 缺收件人顯示「未設定」、notify_abuse 顯示「異常告警」", () => {
    setChannels([TEAMS_CHANNEL, EMAIL_INCOMPLETE]);
    renderWithProviders(<AdminNotificationChannelsPage />);

    const emailRow = screen.getByRole("row", { name: /值班信箱/ });
    expect(within(emailRow).getByText("未設定")).toBeInTheDocument();
    expect(within(emailRow).getByText("異常告警")).toBeInTheDocument();

    const teamsRow = screen.getByRole("row", { name: /Teams 營運群/ });
    expect(within(teamsRow).queryByText("未設定")).not.toBeInTheDocument();
    expect(within(teamsRow).queryByText("異常告警")).not.toBeInTheDocument();
  });

  it("列表：config 缺失時不會崩潰", () => {
    setChannels([
      { ...EMAIL_INCOMPLETE, config: undefined as unknown as Record<string, unknown> },
    ]);
    renderWithProviders(<AdminNotificationChannelsPage />);
    expect(screen.getByText("值班信箱")).toBeInTheDocument();
    expect(screen.getByText("未設定")).toBeInTheDocument();
  });
});
