import { screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { UsageSummaryCards } from "@/features/usage/components/usage-summary-cards";
import { renderWithProviders } from "@/test/test-utils";
import type { BotUsageStat } from "@/types/token-usage";

const ROWS: BotUsageStat[] = [
  {
    bot_id: "b1",
    bot_name: "客服",
    model: "claude-haiku-4-5",
    request_type: "chat_web",
    input_tokens: 1000,
    output_tokens: 500,
    total_tokens: 1500,
    estimated_cost: 0.01,
    message_count: 3,
    points: 12,
  },
  {
    bot_id: null,
    bot_name: null,
    model: "text-embedding-3-small",
    request_type: "embedding",
    input_tokens: 2000,
    output_tokens: 0,
    total_tokens: 2000,
    estimated_cost: 0.001,
    message_count: 1,
    points: 3,
  },
];

describe("UsageSummaryCards（Issue #74 總點數）", () => {
  it("預設（token 制）不顯示總點數卡", () => {
    renderWithProviders(<UsageSummaryCards data={ROWS} isLoading={false} />);
    expect(screen.getByText("總 Tokens")).toBeInTheDocument();
    expect(screen.getByText("3,500")).toBeInTheDocument();
    expect(screen.queryByText("總點數")).not.toBeInTheDocument();
  });

  it("showPoints 時加總各列 points 顯示總點數", () => {
    renderWithProviders(<UsageSummaryCards data={ROWS} isLoading={false} showPoints />);
    expect(screen.getByText("總點數")).toBeInTheDocument();
    expect(screen.getByText("15")).toBeInTheDocument();
  });
});
