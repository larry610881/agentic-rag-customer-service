import { describe, it, expect, vi } from "vitest";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ExecutionNode } from "@/types/agent-trace";
import { TraceTimeline } from "./trace-timeline";

function mk(
  id: string,
  type: string,
  start: number,
  end: number,
  parent: string | null = null,
  label = id,
): ExecutionNode {
  return {
    node_id: id,
    node_type: type as ExecutionNode["node_type"],
    label,
    parent_id: parent,
    start_ms: start,
    end_ms: end,
    duration_ms: end - start,
    token_usage: null,
    metadata: {},
  };
}

const NODES: ExecutionNode[] = [
  mk("req", "request", 0, 1000, null, "Request"),
  mk("verify", "webhook_verify", 0, 100, "req", "驗證簽章"),
  mk("llm", "agent_llm", 100, 900, "req", "LLM 推理"),
  mk("tool", "tool_call", 200, 600, "llm", "search_kb"),
  mk("toolr", "tool_result", 300, 600, "tool", "search_kb 結果"),
];

describe("TraceTimeline", () => {
  it("渲染 root 與第一層列、顯示占比與耗時，深層子列預設收合", () => {
    render(<TraceTimeline nodes={NODES} totalMs={1000} />);
    expect(screen.getByTestId("trace-timeline")).toBeInTheDocument();
    expect(screen.getByTestId("timeline-row-req")).toBeInTheDocument();
    expect(screen.getByTestId("timeline-row-verify")).toBeInTheDocument();
    expect(screen.getByTestId("timeline-row-llm")).toBeInTheDocument();
    // llm 的子節點 tool 不重疊 → 預設收合，子列不出現
    expect(screen.queryByTestId("timeline-row-tool")).not.toBeInTheDocument();

    expect(screen.getByTestId("timeline-pct-verify")).toHaveTextContent("10%");
    expect(screen.getByTestId("timeline-pct-llm")).toHaveTextContent("80%");
    expect(screen.getByTestId("timeline-pct-req")).toHaveTextContent("100%");
    expect(
      within(screen.getByTestId("timeline-row-llm")).getByText("800ms"),
    ).toBeInTheDocument();

    // legend 文字
    expect(screen.getByText("關鍵路徑")).toBeInTheDocument();
    expect(screen.getByText("其他（未儀表化）")).toBeInTheDocument();
    expect(screen.getByText("節點")).toBeInTheDocument();
    expect(screen.getByText("耗時")).toBeInTheDocument();
    expect(screen.getByText("占比")).toBeInTheDocument();
  });

  it("bar 以 left% / width% 定位，收合的父列顯示子節點 inline segment 與 tooltip", () => {
    render(<TraceTimeline nodes={NODES} totalMs={1000} />);
    const seg = screen.getByTestId("timeline-segment-tool");
    expect(seg.style.left).toBe("20%");
    expect(seg.style.width).toBe("40%");
    expect(seg).toHaveAttribute("title", expect.stringContaining("search_kb"));
    expect(seg).toHaveAttribute("title", expect.stringContaining("400ms"));
    expect(seg).toHaveAttribute("title", expect.stringContaining("40%"));

    const verifyBar = screen.getByTestId("timeline-bar-verify");
    expect(verifyBar.style.left).toBe("0%");
    expect(verifyBar.style.width).toBe("10%");
  });

  it("root 列顯示灰色 gap（未儀表化）區段", () => {
    render(<TraceTimeline nodes={NODES} totalMs={1000} />);
    // req 子孫覆蓋 0..900 → gap 900..1000
    const gap = screen.getByTestId("timeline-gap-req-0");
    expect(gap.style.left).toBe("90%");
    expect(gap.style.width).toBe("10%");
    expect(gap).toHaveAttribute("title", expect.stringContaining("其他（未儀表化）"));
  });

  it("關鍵路徑列有 data-critical 標記", () => {
    render(<TraceTimeline nodes={NODES} totalMs={1000} />);
    expect(screen.getByTestId("timeline-row-req")).toHaveAttribute("data-critical", "true");
    expect(screen.getByTestId("timeline-row-llm")).toHaveAttribute("data-critical", "true");
  });

  it("點擊 chevron 展開子列，再點收合", async () => {
    const user = userEvent.setup();
    render(<TraceTimeline nodes={NODES} totalMs={1000} />);
    await user.click(screen.getByTestId("timeline-toggle-llm"));
    expect(screen.getByTestId("timeline-row-tool")).toBeInTheDocument();
    // 展開後 inline segment 消失、換成獨立 bar
    expect(screen.queryByTestId("timeline-segment-tool")).not.toBeInTheDocument();
    expect(screen.getByTestId("timeline-bar-tool")).toBeInTheDocument();
    // 孫節點仍收合
    expect(screen.queryByTestId("timeline-row-toolr")).not.toBeInTheDocument();

    await user.click(screen.getByTestId("timeline-toggle-llm"));
    expect(screen.queryByTestId("timeline-row-tool")).not.toBeInTheDocument();
  });

  it("子節點時間重疊的父列預設自動展開", () => {
    const nodes = [
      mk("req", "request", 0, 100),
      mk("p1", "tool_call", 10, 60, "req"),
      mk("p2", "tool_call", 20, 90, "req"),
    ];
    render(<TraceTimeline nodes={nodes} totalMs={100} />);
    expect(screen.getByTestId("timeline-row-p1")).toBeInTheDocument();
    expect(screen.getByTestId("timeline-row-p2")).toBeInTheDocument();
    expect(screen.getByTestId("timeline-toggle-req")).toHaveAttribute("aria-expanded", "true");
  });

  it("點擊 bar 與 inline segment 都會呼叫 onSelectNode", async () => {
    const user = userEvent.setup();
    const onSelect = vi.fn();
    render(<TraceTimeline nodes={NODES} totalMs={1000} onSelectNode={onSelect} />);
    await user.click(screen.getByTestId("timeline-bar-verify"));
    expect(onSelect).toHaveBeenLastCalledWith("verify");
    await user.click(screen.getByTestId("timeline-segment-tool"));
    expect(onSelect).toHaveBeenLastCalledWith("tool");
    expect(onSelect).toHaveBeenCalledTimes(2);
  });

  it("未知 node_type 與失敗節點都能渲染", () => {
    const nodes = [
      mk("req", "request", 0, 100),
      { ...mk("x", "brand_new_type", 0, 50, "req"), outcome: "failed" as const },
    ];
    render(<TraceTimeline nodes={nodes} totalMs={100} />);
    expect(screen.getByTestId("timeline-row-x")).toBeInTheDocument();
    expect(screen.getByText("FAILED")).toBeInTheDocument();
  });

  it("無 request root 的舊 trace 顯示合成總耗時列", () => {
    const nodes = [mk("u", "user_input", 0, 10), mk("llm", "agent_llm", 50, 100)];
    render(<TraceTimeline nodes={nodes} totalMs={100} />);
    expect(screen.getByTestId("timeline-row-__wall")).toBeInTheDocument();
    expect(screen.getByTestId("timeline-gap-__wall-0").style.left).toBe("10%");
  });

  it("沒有節點時顯示空狀態", () => {
    render(<TraceTimeline nodes={[]} totalMs={0} />);
    expect(screen.getByText("沒有時間資料")).toBeInTheDocument();
  });
});
