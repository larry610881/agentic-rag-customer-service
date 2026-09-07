/** Issue #71 — 變更紀錄清單（hook 以 vi.mock 隔離） */

import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { BotAuditLogList } from "@/features/bot/components/bot-audit-log-list";
import { renderWithProviders } from "@/test/test-utils";
import type { BotAuditLogEntry } from "@/types/bot-audit-log";

const { mockUseBotAuditLogs } = vi.hoisted(() => ({
  mockUseBotAuditLogs: vi.fn(),
}));

vi.mock("@/hooks/queries/use-bot-audit-logs", () => ({
  useBotAuditLogs: (botId: string) => mockUseBotAuditLogs(botId),
}));

const entries: BotAuditLogEntry[] = [
  {
    id: "log-1",
    action: "update",
    actor_user_id: "u-001",
    actor_email: "admin@example.com",
    source: "api",
    created_at: "2026-09-07T10:00:00+00:00",
    changes: [
      { field: "llm_model", before: "gpt-4o", after: "gemini-3.7-flash" },
      { field: "llm_params.temperature", before: 0.3, after: 0.7 },
      { field: "bot_prompt", before_len: 20, after_len: 140, changed: true },
    ],
  },
  {
    id: "log-2",
    action: "update",
    actor_user_id: "u-gone-1234",
    actor_email: null,
    source: "api",
    created_at: "2026-09-06T09:00:00+00:00",
    changes: [],
  },
];

function hookResult(overrides: Record<string, unknown> = {}) {
  return {
    data: { pages: [{ items: entries, next_cursor: null }], pageParams: [undefined] },
    isLoading: false,
    isError: false,
    hasNextPage: false,
    isFetchingNextPage: false,
    fetchNextPage: vi.fn(),
    ...overrides,
  };
}

describe("BotAuditLogList", () => {
  beforeEach(() => {
    mockUseBotAuditLogs.mockReset();
  });

  it("queries the hook with the bot id and renders actor / action / field count", () => {
    mockUseBotAuditLogs.mockReturnValue(hookResult());
    renderWithProviders(<BotAuditLogList botId="bot-1" />);
    expect(mockUseBotAuditLogs).toHaveBeenCalledWith("bot-1");
    expect(screen.getByText("admin@example.com")).toBeInTheDocument();
    expect(screen.getAllByText("更新")).toHaveLength(2);
    expect(screen.getByRole("button", { name: /3 個欄位/ })).toBeInTheDocument();
    // 查無使用者 → 顯示縮短的 id
    expect(screen.getByText("u-gone-1…")).toBeInTheDocument();
    expect(screen.getByText("無欄位變更")).toBeInTheDocument();
  });

  it("expands an entry to show labelled before/after values and long-text deltas", async () => {
    const user = userEvent.setup();
    mockUseBotAuditLogs.mockReturnValue(hookResult());
    renderWithProviders(<BotAuditLogList botId="bot-1" />);
    expect(screen.queryByTestId("bot-audit-detail-log-1")).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /3 個欄位/ }));
    const detail = screen.getByTestId("bot-audit-detail-log-1");
    expect(detail).toHaveTextContent("模型");
    expect(detail).toHaveTextContent("gpt-4o");
    expect(detail).toHaveTextContent("gemini-3.7-flash");
    expect(detail).toHaveTextContent("溫度");
    expect(detail).toHaveTextContent("0.3");
    expect(detail).toHaveTextContent("Bot 自訂指令");
    expect(detail).toHaveTextContent("已修改（+120 字）");
    // 長文字不顯示全文
    expect(detail).not.toHaveTextContent("xxxxxxxxxx");
  });

  it("shows an empty state when there are no entries", () => {
    mockUseBotAuditLogs.mockReturnValue(
      hookResult({ data: { pages: [{ items: [], next_cursor: null }], pageParams: [] } }),
    );
    renderWithProviders(<BotAuditLogList botId="bot-1" />);
    expect(screen.getByTestId("bot-audit-empty")).toBeInTheDocument();
  });

  it("offers 載入更多 when there is a next page", async () => {
    const user = userEvent.setup();
    const fetchNextPage = vi.fn();
    mockUseBotAuditLogs.mockReturnValue(hookResult({ hasNextPage: true, fetchNextPage }));
    renderWithProviders(<BotAuditLogList botId="bot-1" />);
    await user.click(screen.getByRole("button", { name: "載入更多" }));
    expect(fetchNextPage).toHaveBeenCalledTimes(1);
  });

  it("renders loading and error states", () => {
    mockUseBotAuditLogs.mockReturnValue(hookResult({ data: undefined, isLoading: true }));
    const { unmount } = renderWithProviders(<BotAuditLogList botId="bot-1" />);
    expect(screen.getByTestId("bot-audit-loading")).toBeInTheDocument();
    unmount();
    mockUseBotAuditLogs.mockReturnValue(hookResult({ data: undefined, isError: true }));
    renderWithProviders(<BotAuditLogList botId="bot-1" />);
    expect(screen.getByText("載入變更紀錄失敗。")).toBeInTheDocument();
  });
});
