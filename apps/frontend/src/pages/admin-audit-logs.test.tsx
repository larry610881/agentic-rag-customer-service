import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import AdminAuditLogsPage from "@/pages/admin-audit-logs";
import { renderWithProviders } from "@/test/test-utils";
import type { AuditLog } from "@/types/audit-log";

vi.mock("@/hooks/queries/use-audit-logs", () => ({
  useAuditLogs: vi.fn(),
}));
vi.mock("@/hooks/queries/use-tenants", () => ({
  useTenants: vi.fn(() => ({
    data: { items: [{ id: "tenant-1", name: "家樂福" }] },
  })),
}));

import { useAuditLogs } from "@/hooks/queries/use-audit-logs";
const useAuditLogsMock = vi.mocked(useAuditLogs);

const LOGS: AuditLog[] = [
  {
    id: "log-1",
    tenant_id: "tenant-1",
    actor_user_id: "user-aaaaaaaaaaaaaaaa",
    entity_type: "guard_rules",
    entity_id: "bot-1",
    action: "update",
    changed_fields: {
      "input_rules.role_hijack.enabled": { before: false, after: true },
      blocked_response: { before: "舊回覆", after: "新回覆" },
    },
    source: "admin_ui",
    created_at: "2026-09-01T08:00:00Z",
  },
  {
    id: "log-2",
    tenant_id: null,
    actor_user_id: null,
    entity_type: "system_prompt",
    entity_id: null,
    action: "reset",
    changed_fields: {},
    source: "api",
    created_at: "2026-09-01T09:00:00Z",
  },
];

describe("AdminAuditLogsPage", () => {
  beforeEach(() => {
    useAuditLogsMock.mockReset();
    useAuditLogsMock.mockReturnValue({
      data: { items: LOGS, limit: 20, offset: 0 },
      isLoading: false,
      error: null,
      isFetching: false,
    } as unknown as ReturnType<typeof useAuditLogs>);
  });

  it("渲染標題、篩選器與紀錄列", () => {
    renderWithProviders(<AdminAuditLogsPage />);
    expect(screen.getByRole("heading", { name: "稽核紀錄" })).toBeInTheDocument();
    expect(screen.getByLabelText("對象 ID")).toBeInTheDocument();

    const row1 = screen.getByTestId("audit-row-log-1");
    expect(within(row1).getByText("家樂福")).toBeInTheDocument();
    expect(within(row1).getByText("安全規則")).toBeInTheDocument();
    expect(within(row1).getByText("更新")).toBeInTheDocument();
    expect(within(row1).getByText("admin_ui")).toBeInTheDocument();
    expect(within(row1).getByText("bot-1")).toBeInTheDocument();

    const row2 = screen.getByTestId("audit-row-log-2");
    expect(within(row2).getByText("系統提示詞")).toBeInTheDocument();
    expect(within(row2).getByText("重設")).toBeInTheDocument();
    // 無變更欄位 → 沒有展開按鈕
    expect(within(row2).queryByRole("button", { name: /個欄位/ })).not.toBeInTheDocument();
  });

  it("點擊變更欄位數量展開 before/after", async () => {
    const user = userEvent.setup();
    renderWithProviders(<AdminAuditLogsPage />);
    const row1 = screen.getByTestId("audit-row-log-1");
    const toggle = within(row1).getByRole("button", { name: /2 個欄位/ });
    expect(screen.queryByTestId("audit-detail-log-1")).not.toBeInTheDocument();

    await user.click(toggle);
    const detail = screen.getByTestId("audit-detail-log-1");
    expect(within(detail).getByText("blocked_response")).toBeInTheDocument();
    expect(within(detail).getByText("舊回覆")).toBeInTheDocument();
    expect(within(detail).getByText("新回覆")).toBeInTheDocument();
    expect(within(detail).getByText("input_rules.role_hijack.enabled")).toBeInTheDocument();

    await user.click(toggle);
    expect(screen.queryByTestId("audit-detail-log-1")).not.toBeInTheDocument();
  });

  it("對象 ID 套用後以 entity_id 篩選並回到第 1 頁", async () => {
    const user = userEvent.setup();
    renderWithProviders(<AdminAuditLogsPage />);
    await user.type(screen.getByLabelText("對象 ID"), "bot-9{Enter}");
    const lastCall = useAuditLogsMock.mock.calls.at(-1)?.[0];
    expect(lastCall).toMatchObject({ entity_id: "bot-9", offset: 0, limit: 20 });
  });

  it("空結果顯示空狀態", () => {
    useAuditLogsMock.mockReturnValue({
      data: { items: [], limit: 20, offset: 0 },
      isLoading: false,
      error: null,
      isFetching: false,
    } as unknown as ReturnType<typeof useAuditLogs>);
    renderWithProviders(<AdminAuditLogsPage />);
    expect(screen.getByTestId("audit-empty")).toBeInTheDocument();
  });
});
