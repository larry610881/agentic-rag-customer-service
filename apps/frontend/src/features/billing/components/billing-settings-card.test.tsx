import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { BillingSettingsCard } from "@/features/billing/components/billing-settings-card";
import { renderWithProviders } from "@/test/test-utils";

vi.mock("@/hooks/queries/use-billing-settings", () => ({
  useBillingSettings: vi.fn(),
  useUpdateBillingSettings: vi.fn(),
}));

import {
  useBillingSettings,
  useUpdateBillingSettings,
} from "@/hooks/queries/use-billing-settings";

const settingsMock = vi.mocked(useBillingSettings);
const updateMock = vi.mocked(useUpdateBillingSettings);
const mutateAsync = vi.fn();

describe("BillingSettingsCard（Issue #74 平台匯率）", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mutateAsync.mockResolvedValue({
      usd_per_point: 0.002,
      updated_by: "admin",
      updated_at: "2026-09-07T00:00:00Z",
    });
    settingsMock.mockReturnValue({
      // Decimal 序列化為字串也要能吃
      data: { usd_per_point: "0.001", updated_by: "admin", updated_at: "2026-09-07T00:00:00Z" },
      isLoading: false,
      isError: false,
    } as unknown as ReturnType<typeof useBillingSettings>);
    updateMock.mockReturnValue({
      mutateAsync,
      isPending: false,
    } as unknown as ReturnType<typeof useUpdateBillingSettings>);
  });

  it("載入匯率後帶入輸入框，未變更時儲存停用", () => {
    renderWithProviders(<BillingSettingsCard />);
    expect(screen.getByLabelText(/每點 USD/)).toHaveValue(0.001);
    expect(screen.getByText("目前：1 點 = 0.001000 USD")).toBeInTheDocument();
    expect(screen.getByText(/（admin）/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "儲存匯率" })).toBeDisabled();
  });

  it("修改匯率後儲存 → PUT { usd_per_point }", async () => {
    const user = userEvent.setup();
    renderWithProviders(<BillingSettingsCard />);
    const input = screen.getByLabelText(/每點 USD/);
    await user.clear(input);
    await user.type(input, "0.002");
    await user.click(screen.getByRole("button", { name: "儲存匯率" }));

    await waitFor(() => expect(mutateAsync).toHaveBeenCalledTimes(1));
    expect(mutateAsync.mock.calls[0][0]).toEqual({ usd_per_point: 0.002 });
  });

  it("匯率為 0 或空白時儲存停用", async () => {
    const user = userEvent.setup();
    renderWithProviders(<BillingSettingsCard />);
    const input = screen.getByLabelText(/每點 USD/);
    await user.clear(input);
    expect(screen.getByRole("button", { name: "儲存匯率" })).toBeDisabled();
    await user.type(input, "0");
    expect(screen.getByRole("button", { name: "儲存匯率" })).toBeDisabled();
  });

  it("載入失敗顯示錯誤", () => {
    settingsMock.mockReturnValue({
      data: undefined,
      isLoading: false,
      isError: true,
    } as unknown as ReturnType<typeof useBillingSettings>);
    renderWithProviders(<BillingSettingsCard />);
    expect(screen.getByText("載入匯率失敗")).toBeInTheDocument();
  });
});
