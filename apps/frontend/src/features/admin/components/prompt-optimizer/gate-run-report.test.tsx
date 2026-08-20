import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import type { GateRun } from "@/types/config-version";

import { GateRunReport } from "./gate-run-report";

// AgentTraceGraph 依賴 React Flow（jsdom 不支援），以 stub 隔離
vi.mock("@/features/admin/components/agent-trace-graph", () => ({
  AgentTraceGraph: () => <div data-testid="trace-graph" />,
}));

function makeRun(overrides: Partial<GateRun> = {}): GateRun {
  return {
    id: "run-1",
    bot_id: "bot-1",
    version_id: "ver-1",
    status: "completed",
    verdict: "pass",
    fail_reasons: [],
    dataset_ids: ["ds-1"],
    repeats: 3,
    soft_threshold: 0.8,
    total_cases: 1,
    hard_failed_cases: 0,
    soft_pass_rate: 1,
    unstable_cases: 0,
    est_cost: 0.01,
    actual_cost: 0.008,
    details: {
      aborted: false,
      excluded_platform_cases: [],
      cases: [
        {
          case_id: "d:c1",
          question: "測試問題一",
          priority: "P0",
          pass_rate: 1,
          soft_passed: true,
          hard_failed: false,
          unstable: false,
          rounds: [
            {
              round: 0,
              response_text: "模型的回答內容",
              truncated: false,
              latency_ms: 120,
              tokens: 150,
              cost: 0.001,
              trace_id: "tr-1",
              trace_nodes: [{ node_id: "n1" }],
              assertions: [
                {
                  type: "no_role_switch",
                  severity: "hard",
                  passed: true,
                  message: "ok",
                },
              ],
            },
          ],
        },
      ],
    },
    error_message: null,
    created_at: "2026-08-20T00:00:00Z",
    started_at: null,
    completed_at: null,
    ...overrides,
  };
}

describe("GateRunReport", () => {
  it("通過時顯示綠色 verdict 與統計", () => {
    render(<GateRunReport run={makeRun()} />);
    expect(screen.getByText(/驗證通過/)).toBeInTheDocument();
    expect(screen.getByText(/硬失敗 0 題/)).toBeInTheDocument();
  });

  it("失敗時列出失敗原因", () => {
    render(
      <GateRunReport
        run={makeRun({
          verdict: "fail",
          fail_reasons: ["hard_gate", "budget_exceeded"],
          hard_failed_cases: 1,
        })}
      />,
    );
    expect(screen.getByText(/驗證未通過/)).toBeInTheDocument();
    expect(screen.getByText(/硬閘門未過/)).toBeInTheDocument();
    expect(screen.getByText(/超出驗證預算/)).toBeInTheDocument();
  });

  it("展開題目可見回應全文與斷言徽章", async () => {
    const user = userEvent.setup();
    render(<GateRunReport run={makeRun()} />);
    await user.click(screen.getByRole("button", { name: /測試問題一/ }));
    expect(screen.getByText("模型的回答內容")).toBeInTheDocument();
    expect(screen.getByText(/no_role_switch/)).toBeInTheDocument();
  });

  it("執行中顯示進度提示", () => {
    render(
      <GateRunReport
        run={makeRun({ status: "running", verdict: null, details: null })}
      />,
    );
    expect(screen.getByText(/驗證執行中/)).toBeInTheDocument();
  });

  it("錯誤時顯示錯誤訊息", () => {
    render(
      <GateRunReport
        run={makeRun({
          status: "error",
          verdict: null,
          details: null,
          error_message: "api down",
        })}
      />,
    );
    expect(screen.getByText(/驗證執行失敗/)).toBeInTheDocument();
  });
});
