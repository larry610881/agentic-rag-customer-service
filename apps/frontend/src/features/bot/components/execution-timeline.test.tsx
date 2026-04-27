import { render, screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";

import { ExecutionTimeline } from "./execution-timeline";
import type { SSEEvent } from "@/lib/sse-client";

describe("ExecutionTimeline guard_blocked rendering", () => {
  it("renders 🛡️ 攔截 label and rule_matched detail for guard_blocked event", () => {
    const events: SSEEvent[] = [
      { type: "tool_calls", tool_calls: [{ tool_name: "rag_query" }], ts_ms: 100 },
      {
        type: "guard_blocked",
        block_type: "input",
        rule_matched: "忽略(以上|上面)指令",
        ts_ms: 200,
      },
      { type: "done", trace_id: "abc12345", ts_ms: 250 },
    ];

    render(<ExecutionTimeline events={events} />);

    expect(screen.getByText("🛡️ 攔截")).toBeInTheDocument();
    expect(screen.getByText(/input.*忽略/)).toBeInTheDocument();
  });

  it("guard_blocked card uses red ring danger styling (visually distinct)", () => {
    const events: SSEEvent[] = [
      {
        type: "guard_blocked",
        block_type: "input",
        rule_matched: "DAN mode",
        ts_ms: 50,
      },
    ];

    const { container } = render(<ExecutionTimeline events={events} />);
    const cards = container.querySelectorAll("[class*='ring']");
    // 攔截卡片必須有 ring（紅環）強調，跟一般 error card 區分
    expect(cards.length).toBeGreaterThan(0);
  });

  it("falls back to 'input blocked' when rule_matched missing", () => {
    const events: SSEEvent[] = [
      { type: "guard_blocked", block_type: "output", ts_ms: 50 },
    ];

    render(<ExecutionTimeline events={events} />);
    expect(screen.getByText(/output blocked/)).toBeInTheDocument();
  });
});
