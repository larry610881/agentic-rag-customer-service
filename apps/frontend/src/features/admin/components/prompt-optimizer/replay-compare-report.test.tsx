/** M53：真實流量回放 pairwise 對比報告的渲染測試（原本零覆蓋）。 */

import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import type { GateRun } from "@/types/config-version";

import { ReplayCompareReport } from "./replay-compare-report";

function makeRun(overrides: Partial<GateRun> = {}): GateRun {
  return {
    id: "run-r1",
    bot_id: "bot-1",
    version_id: "ver-1",
    status: "completed",
    verdict: "pass",
    fail_reasons: [],
    dataset_ids: [],
    repeats: 1,
    soft_threshold: 0.8,
    total_cases: 2,
    hard_failed_cases: 0,
    soft_pass_rate: 1,
    unstable_cases: 0,
    est_cost: 0.01,
    actual_cost: 0.0123,
    details: {
      type: "replay_compare",
      aborted: false,
      summary: {
        candidate_wins: 1,
        baseline_wins: 0,
        ties: 1,
        win_rate: 0.5,
      },
      items: [
        {
          question: "退貨要怎麼辦理？",
          baseline_answer: "線上版回答",
          candidate_answer: "草稿版回答",
          verdict: "candidate",
          judge_normal: "candidate",
          judge_swapped: "candidate",
          baseline_cost: 0.001,
          candidate_cost: 0.0012,
        },
        {
          question: "有實體門市嗎？",
          baseline_answer: "有的",
          candidate_answer: "有喔",
          verdict: "tie",
          judge_normal: "candidate",
          judge_swapped: "baseline",
          baseline_cost: 0.001,
          candidate_cost: 0.001,
        },
      ],
    },
    error_message: null,
    created_at: "2026-08-20T00:00:00Z",
    started_at: null,
    completed_at: null,
    ...overrides,
  } as GateRun;
}

describe("ReplayCompareReport", () => {
  it("顯示勝負統計與逐題列", () => {
    render(<ReplayCompareReport run={makeRun()} />);
    expect(screen.getByText(/草稿 1 勝 · 線上 0 勝 · 1 平/)).toBeInTheDocument();
    expect(screen.getByText("退貨要怎麼辦理？")).toBeInTheDocument();
    expect(screen.getByText("草稿勝")).toBeInTheDocument();
    expect(screen.getByText("平手")).toBeInTheDocument();
  });

  it("展開一題顯示兩版並排回應", async () => {
    const user = userEvent.setup();
    render(<ReplayCompareReport run={makeRun()} />);
    await user.click(
      screen.getByRole("button", { name: /退貨要怎麼辦理/ }),
    );
    expect(screen.getByText("線上版回答")).toBeInTheDocument();
    expect(screen.getByText("草稿版回答")).toBeInTheDocument();
  });

  it("aborted 顯示預算中止提示", () => {
    const run = makeRun();
    (run.details as { aborted: boolean }).aborted = true;
    render(<ReplayCompareReport run={run} />);
    expect(screen.getByText(/超出預算提前中止/)).toBeInTheDocument();
  });

  it("執行中顯示進度、錯誤顯示訊息", () => {
    const { rerender } = render(
      <ReplayCompareReport
        run={makeRun({ status: "running", details: null })}
      />,
    );
    expect(screen.getByText(/回放對比執行中/)).toBeInTheDocument();
    rerender(
      <ReplayCompareReport
        run={makeRun({
          status: "error",
          details: null,
          error_message: "judge down",
        })}
      />,
    );
    expect(screen.getByText(/回放對比失敗：judge down/)).toBeInTheDocument();
  });
});
