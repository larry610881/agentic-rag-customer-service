import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import WidgetIdentityPage from "@/pages/widget-identity";
import { renderWithProviders } from "@/test/test-utils";
import { formatDateTime } from "@/lib/format-date";
import { useAuthStore } from "@/stores/use-auth-store";
import type { WidgetIdentityStatus } from "@/types/widget-identity";

vi.mock("@/hooks/queries/use-widget-identity", () => ({
  useWidgetIdentityStatus: vi.fn(),
  useRotateWidgetIdentitySecret: vi.fn(),
  useUpdateWidgetIdentityPolicy: vi.fn(),
}));

vi.mock("@/hooks/queries/use-tenants", () => ({
  useTenants: vi.fn(() => ({
    data: { items: [{ id: "t-1", name: "家樂福" }], total: 1, page: 1, page_size: 100, total_pages: 1 },
  })),
}));

import {
  useRotateWidgetIdentitySecret,
  useUpdateWidgetIdentityPolicy,
  useWidgetIdentityStatus,
} from "@/hooks/queries/use-widget-identity";

const statusMock = vi.mocked(useWidgetIdentityStatus);
const rotateMock = vi.mocked(useRotateWidgetIdentitySecret);
const updateMock = vi.mocked(useUpdateWidgetIdentityPolicy);

const rotateMutate = vi.fn();
const updateMutate = vi.fn();

const ROTATED_AT = "2026-09-04T01:02:03Z";

const STATUS: WidgetIdentityStatus = {
  tenant_id: "t-1",
  has_secret: true,
  is_enabled: true,
  enforce_verified: false,
  rotated_at: ROTATED_AT,
};

const NO_SECRET: WidgetIdentityStatus = {
  tenant_id: "t-1",
  has_secret: false,
  is_enabled: false,
  enforce_verified: false,
  rotated_at: null,
};

function mockStatus(data: WidgetIdentityStatus) {
  statusMock.mockReturnValue({
    data,
    isLoading: false,
    isError: false,
  } as unknown as ReturnType<typeof useWidgetIdentityStatus>);
}

describe("WidgetIdentityPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    useAuthStore.setState({ token: "tok", tenantId: "t-1", role: "tenant_admin" });
    mockStatus(STATUS);
    rotateMock.mockReturnValue({
      mutate: rotateMutate,
      isPending: false,
    } as unknown as ReturnType<typeof useRotateWidgetIdentitySecret>);
    updateMock.mockReturnValue({
      mutate: updateMutate,
      isPending: false,
    } as unknown as ReturnType<typeof useUpdateWidgetIdentityPolicy>);
  });

  it("tenant_admin 不帶 tenant_id 讀取狀態，並顯示 secret／啟用／強制驗證／輪替時間", () => {
    renderWithProviders(<WidgetIdentityPage />);

    expect(statusMock).toHaveBeenCalledWith(undefined, true);
    expect(screen.getByTestId("status-has-secret")).toHaveTextContent("已設定");
    expect(screen.getByTestId("status-is-enabled")).toHaveTextContent("已啟用");
    expect(screen.getByTestId("status-enforce-verified")).toHaveTextContent("關閉");
    expect(screen.getByTestId("status-rotated-at")).toHaveTextContent(
      formatDateTime(ROTATED_AT),
    );

    expect(screen.getByRole("switch", { name: "啟用身分綁定" })).toBeChecked();
    expect(screen.getByRole("switch", { name: "強制驗證" })).not.toBeChecked();
    expect(screen.getByRole("button", { name: "輪替 secret" })).toBeInTheDocument();
  });

  it("尚未產生 secret 時兩個開關 disabled、顯示提示，按鈕改為「產生 secret」", () => {
    mockStatus(NO_SECRET);
    renderWithProviders(<WidgetIdentityPage />);

    expect(screen.getByTestId("status-has-secret")).toHaveTextContent("尚未產生");
    expect(screen.getByTestId("status-rotated-at")).toHaveTextContent("—");
    expect(screen.getByRole("switch", { name: "啟用身分綁定" })).toBeDisabled();
    expect(screen.getByRole("switch", { name: "強制驗證" })).toBeDisabled();
    expect(screen.getByTestId("no-secret-hint")).toHaveTextContent("請先產生 secret");
    expect(screen.getByRole("button", { name: "產生 secret" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "輪替 secret" })).not.toBeInTheDocument();
  });

  it("切換開關只送出該欄位的 PUT", async () => {
    const user = userEvent.setup();
    renderWithProviders(<WidgetIdentityPage />);

    await user.click(screen.getByRole("switch", { name: "強制驗證" }));
    expect(updateMutate).toHaveBeenCalledTimes(1);
    expect(updateMutate.mock.calls[0][0]).toEqual({
      tenantId: undefined,
      data: { enforce_verified: true },
    });

    await user.click(screen.getByRole("switch", { name: "啟用身分綁定" }));
    expect(updateMutate).toHaveBeenCalledTimes(2);
    expect(updateMutate.mock.calls[1][0]).toEqual({
      tenantId: undefined,
      data: { is_enabled: false },
    });
  });

  it("輪替：取消不呼叫 mutation，確認後呼叫並只顯示一次 secret", async () => {
    const user = userEvent.setup();
    rotateMutate.mockImplementation((vars, opts) => {
      opts?.onSuccess?.({ tenant_id: "t-1", secret: "s3cr3t-once" }, vars, undefined);
    });
    renderWithProviders(<WidgetIdentityPage />);

    await user.click(screen.getByRole("button", { name: "輪替 secret" }));
    const confirm = screen.getByRole("alertdialog");
    expect(within(confirm).getByText(/舊的 secret 會立即失效/)).toBeInTheDocument();

    await user.click(within(confirm).getByRole("button", { name: "取消" }));
    expect(rotateMutate).not.toHaveBeenCalled();
    expect(screen.queryByRole("alertdialog")).not.toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "輪替 secret" }));
    await user.click(
      within(screen.getByRole("alertdialog")).getByRole("button", { name: "確認輪替" }),
    );

    expect(rotateMutate).toHaveBeenCalledTimes(1);
    expect(rotateMutate.mock.calls[0][0]).toEqual({ tenantId: undefined });

    const dialog = await screen.findByRole("dialog");
    expect(within(dialog).getByLabelText("secret")).toHaveValue("s3cr3t-once");
    expect(within(dialog).getByRole("alert")).toHaveTextContent("關閉後無法再次查看");
    expect(within(dialog).getByRole("button", { name: "複製 secret" })).toBeInTheDocument();

    await user.click(within(dialog).getByRole("button", { name: "我已保存，關閉" }));
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("system_admin 看得到租戶選擇器，未選租戶前不讀狀態；tenant_admin 沒有選擇器", () => {
    useAuthStore.setState({ role: "system_admin", tenantId: null });
    statusMock.mockReturnValue({
      data: undefined,
      isLoading: false,
      isError: false,
    } as unknown as ReturnType<typeof useWidgetIdentityStatus>);
    const { unmount } = renderWithProviders(<WidgetIdentityPage />);

    expect(screen.getByRole("combobox")).toBeInTheDocument();
    expect(screen.getByText("請先選擇租戶")).toBeInTheDocument();
    expect(statusMock).toHaveBeenCalledWith(undefined, false);
    expect(screen.queryByTestId("status-has-secret")).not.toBeInTheDocument();
    unmount();

    useAuthStore.setState({ role: "tenant_admin", tenantId: "t-1" });
    mockStatus(STATUS);
    renderWithProviders(<WidgetIdentityPage />);
    expect(screen.queryByRole("combobox")).not.toBeInTheDocument();
    expect(screen.getByTestId("status-has-secret")).toBeInTheDocument();
  });

  it("宿主整合方式可展開，含 Node.js / Python / widget identify 範例", async () => {
    const user = userEvent.setup();
    renderWithProviders(<WidgetIdentityPage />);

    await user.click(screen.getByRole("button", { name: /宿主整合方式/ }));
    expect(screen.getByText(/crypto\.createHmac\("sha256"/)).toBeInTheDocument();
    expect(screen.getByText(/hmac\.new\(os\.environ/)).toBeInTheDocument();
    expect(screen.getByText(/window\.AgenticRagWidget\.identify/)).toBeInTheDocument();
  });
});
