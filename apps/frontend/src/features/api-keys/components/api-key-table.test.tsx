import { describe, it, expect, vi, beforeEach } from "vitest";
import { screen, within } from "@testing-library/react";
import { renderWithProviders, userEvent } from "@/test/test-utils";
import { ApiKeyTable } from "@/features/api-keys/components/api-key-table";
import type { ApiKey } from "@/types/api-key";

const revokeMutate = vi.fn();
let keysData: ApiKey[] = [];
let isLoading = false;

vi.mock("@/hooks/queries/use-api-keys", () => ({
  useApiKeys: () => ({ data: keysData, isLoading, isError: false }),
  useRevokeApiKey: () => ({ mutate: revokeMutate, isPending: false }),
}));

const baseKey: ApiKey = {
  id: "key-1",
  client_id: "key-1",
  tenant_id: "tenant-1",
  name: "官網整合",
  description: "給官網 widget 用",
  secret_prefix: "ak_live_abc",
  scopes: ["chat:send", "chat:stream"],
  allowed_bot_ids: [],
  expires_at: null,
  revoked_at: null,
  is_active: true,
  last_used_at: null,
  created_by: "user-1",
  created_at: "2026-09-01T08:00:00Z",
};

describe("ApiKeyTable", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    isLoading = false;
    keysData = [
      baseKey,
      {
        ...baseKey,
        id: "key-2",
        client_id: "key-2",
        name: "已撤銷的金鑰",
        description: null,
        allowed_bot_ids: ["bot-a", "bot-b"],
        revoked_at: "2026-09-02T00:00:00Z",
        is_active: false,
        last_used_at: "2026-09-01T12:00:00Z",
      },
      {
        ...baseKey,
        id: "key-3",
        client_id: "key-3",
        name: "過期金鑰",
        expires_at: "2020-01-01T00:00:00Z",
      },
    ];
  });

  it("renders one row per key with prefix, scopes, bot count and status", () => {
    renderWithProviders(<ApiKeyTable />);

    const rows = screen.getAllByRole("row").slice(1); // skip header
    expect(rows).toHaveLength(3);

    const first = within(rows[0]);
    expect(first.getByText("官網整合")).toBeInTheDocument();
    expect(first.getByText("ak_live_abc…")).toBeInTheDocument();
    expect(first.getByText("chat:send")).toBeInTheDocument();
    expect(first.getByText("chat:stream")).toBeInTheDocument();
    expect(first.getByText("全部")).toBeInTheDocument();
    expect(first.getByText("使用中")).toBeInTheDocument();
    expect(first.getByText("從未使用")).toBeInTheDocument();

    const second = within(rows[1]);
    expect(second.getByText("2 個")).toBeInTheDocument();
    expect(second.getByText("已撤銷")).toBeInTheDocument();
    expect(second.queryByRole("button", { name: "撤銷" })).not.toBeInTheDocument();

    expect(within(rows[2]).getByText("已過期")).toBeInTheDocument();
  });

  it("shows empty state when no keys", () => {
    keysData = [];
    renderWithProviders(<ApiKeyTable />);
    expect(screen.getByText("尚未建立任何 API 金鑰。")).toBeInTheDocument();
  });

  it("revoke button opens confirm dialog and calls mutation with the key id", async () => {
    const user = userEvent.setup();
    renderWithProviders(<ApiKeyTable />);

    await user.click(screen.getByRole("button", { name: "撤銷" }));
    const dialog = screen.getByRole("alertdialog");
    expect(within(dialog).getByText(/官網整合/)).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "確認撤銷" }));
    expect(revokeMutate).toHaveBeenCalledTimes(1);
    expect(revokeMutate.mock.calls[0][0]).toBe("key-1");
  });
});
