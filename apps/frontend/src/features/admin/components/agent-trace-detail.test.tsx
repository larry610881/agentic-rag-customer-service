import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import type { AgentExecutionTrace } from "@/types/agent-trace";
import { AgentTraceDetail } from "./agent-trace-detail";

vi.mock("./agent-trace-graph", () => ({
  AgentTraceGraph: () => <div data-testid="graph-stub" />,
}));
vi.mock("./config-snapshot-panel", () => ({
  ConfigSnapshotPanel: ({ hash }: { hash: string }) => (
    <div data-testid="snapshot-stub">{hash}</div>
  ),
}));
vi.mock("sonner", () => ({ toast: { success: vi.fn(), error: vi.fn() } }));

const BASE: AgentExecutionTrace = {
  id: "t1",
  trace_id: "trace-1",
  tenant_id: "tenant-1",
  message_id: null,
  conversation_id: null,
  agent_mode: "react",
  source: "web",
  llm_model: "gpt-4o-mini",
  llm_provider: "openai",
  bot_id: "bot-1",
  nodes: [],
  total_ms: 1234,
  total_tokens: null,
  created_at: "2026-09-01T00:00:00Z",
};

describe("AgentTraceDetail — 生效設定 tab（Issue #60）", () => {
  it("沒有 config_hash 時不顯示生效設定 tab", () => {
    render(<AgentTraceDetail trace={BASE} onBack={() => {}} />);
    expect(screen.getByRole("tab", { name: "節點圖" })).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: "時間軸" })).toBeInTheDocument();
    expect(screen.queryByRole("tab", { name: "生效設定" })).not.toBeInTheDocument();
    expect(screen.queryByTestId("config-hash-chip")).not.toBeInTheDocument();
  });

  it("有 config_hash 時顯示 hash chip 與生效設定 tab", () => {
    const hash = "deadbeefdeadbeefdeadbeefdeadbeef";
    render(
      <AgentTraceDetail trace={{ ...BASE, config_hash: hash }} onBack={() => {}} />,
    );
    expect(screen.getByRole("tab", { name: "生效設定" })).toBeInTheDocument();
    expect(screen.getByTestId("config-hash-chip")).toHaveTextContent(hash.slice(0, 12));
  });
});
