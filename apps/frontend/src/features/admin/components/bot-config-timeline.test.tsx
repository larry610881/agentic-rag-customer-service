import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { BotConfigTimeline } from "./bot-config-timeline";

vi.mock("@/hooks/queries/use-config-snapshots", () => ({
  useBotConfigTimeline: vi.fn(),
  useConfigSnapshotDiff: vi.fn(),
}));
vi.mock("sonner", () => ({ toast: { success: vi.fn(), error: vi.fn() } }));

import {
  useBotConfigTimeline,
  useConfigSnapshotDiff,
} from "@/hooks/queries/use-config-snapshots";
const timelineMock = vi.mocked(useBotConfigTimeline);
const diffMock = vi.mocked(useConfigSnapshotDiff);

const H_NEW = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa";
const H_OLD = "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb";
const LONG = "x".repeat(300);

describe("BotConfigTimeline", () => {
  beforeEach(() => {
    timelineMock.mockReset();
    diffMock.mockReset();
    timelineMock.mockReturnValue({
      data: {
        bot_id: "bot-1",
        items: [
          {
            hash: H_NEW,
            first_seen_at: "2026-09-02T00:00:00Z",
            last_seen_at: "2026-09-02T12:00:00Z",
            turns: 42,
          },
          {
            hash: H_OLD,
            first_seen_at: "2026-08-20T00:00:00Z",
            last_seen_at: "2026-09-01T23:00:00Z",
            turns: 310,
          },
        ],
      },
      isLoading: false,
      error: null,
    } as unknown as ReturnType<typeof useBotConfigTimeline>);
    diffMock.mockImplementation(((a: string, b: string, enabled: boolean) => ({
      data:
        enabled && a && b
          ? {
              a,
              b,
              changed_fields: {
                "retrieval.rerank_enabled": { before: false, after: true },
                system_prompt: { before: "短", after: LONG },
              },
            }
          : undefined,
      isLoading: false,
      error: null,
    })) as unknown as typeof useConfigSnapshotDiff);
  });

  it("列出 hash（同 hash 同色）、生效區間、輪數", () => {
    render(<BotConfigTimeline botId="bot-1" />);
    const rowNew = screen.getByTestId(`timeline-row-${H_NEW}`);
    expect(within(rowNew).getByText("42")).toBeInTheDocument();
    expect(within(rowNew).getByTestId("config-hash-chip")).toHaveTextContent(
      H_NEW.slice(0, 12),
    );
    const rowOld = screen.getByTestId(`timeline-row-${H_OLD}`);
    expect(within(rowOld).getByText("310")).toBeInTheDocument();

    const chipNew = within(rowNew).getByTestId("config-hash-chip");
    const chipOld = within(rowOld).getByTestId("config-hash-chip");
    expect(chipNew.style.backgroundColor).not.toBe("");
    expect(chipNew.style.backgroundColor).not.toBe(chipOld.style.backgroundColor);
  });

  it("勾選兩筆 → 比較 → 以舊→新呼叫 diff 並渲染變更欄位表；長字串可展開", async () => {
    const user = userEvent.setup();
    render(<BotConfigTimeline botId="bot-1" />);

    const compareBtn = screen.getByRole("button", { name: /比較/ });
    expect(compareBtn).toBeDisabled();

    await user.click(screen.getByRole("checkbox", { name: `選取 ${H_NEW}` }));
    expect(compareBtn).toBeDisabled();
    await user.click(screen.getByRole("checkbox", { name: `選取 ${H_OLD}` }));
    expect(compareBtn).toBeEnabled();

    await user.click(compareBtn);

    // a=較舊、b=較新
    expect(diffMock).toHaveBeenLastCalledWith(H_OLD, H_NEW, true);

    const table = await screen.findByTestId("config-diff-table");
    expect(within(table).getByText("欄位")).toBeInTheDocument();
    expect(within(table).getByText("變更前")).toBeInTheDocument();
    expect(within(table).getByText("變更後")).toBeInTheDocument();

    const rerankRow = screen.getByTestId("config-diff-row-retrieval.rerank_enabled");
    expect(within(rerankRow).getByText("false")).toBeInTheDocument();
    expect(within(rerankRow).getByText("true")).toBeInTheDocument();

    const promptRow = screen.getByTestId("config-diff-row-system_prompt");
    const expandBtn = within(promptRow).getByRole("button", { name: "展開" });
    expect(promptRow).not.toHaveTextContent(LONG);
    await user.click(expandBtn);
    expect(promptRow).toHaveTextContent(LONG);
    expect(within(promptRow).getByRole("button", { name: "收合" })).toBeInTheDocument();
  });

  it("沒有紀錄時顯示空狀態", () => {
    timelineMock.mockReturnValue({
      data: { bot_id: "bot-1", items: [] },
      isLoading: false,
      error: null,
    } as unknown as ReturnType<typeof useBotConfigTimeline>);
    render(<BotConfigTimeline botId="bot-1" />);
    expect(screen.getByTestId("timeline-empty")).toBeInTheDocument();
  });
});
