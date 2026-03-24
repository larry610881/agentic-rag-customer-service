import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect } from "vitest";
import { CaseResultsTable } from "./case-results-table";
import type { CaseResultData } from "./case-results-table";

const mockCaseResults: CaseResultData[] = [
  {
    case_id: "case-001",
    question: "退貨政策是什麼？",
    priority: "P0",
    category: "general",
    score: 1.0,
    passed_count: 2,
    total_count: 2,
    p0_failed: false,
    answer_snippet: "您可以在 30 天內申請退貨...",
    assertion_results: [
      { passed: true, assertion_type: "contains_text", message: "包含退貨" },
      { passed: true, assertion_type: "no_hallucination", message: "OK" },
    ],
  },
  {
    case_id: "case-002",
    question: "如何聯繫客服？",
    priority: "P1",
    category: "support",
    score: 0.5,
    passed_count: 1,
    total_count: 2,
    p0_failed: false,
    answer_snippet: "請撥打客服電話...",
    assertion_results: [
      { passed: true, assertion_type: "contains_text", message: "包含電話" },
      { passed: false, assertion_type: "max_tokens", message: "超過 token 上限" },
    ],
  },
  {
    case_id: "case-003",
    question: "運費怎麼算？",
    priority: "P0",
    category: "shipping",
    score: 0.0,
    passed_count: 0,
    total_count: 2,
    p0_failed: true,
    answer_snippet: "不好意思我不太確定...",
    assertion_results: [
      { passed: false, assertion_type: "contains_text", message: "缺少運費資訊" },
      { passed: false, assertion_type: "no_hallucination", message: "回答不確定" },
    ],
  },
];

describe("CaseResultsTable", () => {
  it("應正確渲染所有案例行，含 case_id 和 priority", () => {
    render(<CaseResultsTable caseResults={mockCaseResults} />);

    expect(screen.getByText("case-001")).toBeInTheDocument();
    expect(screen.getByText("case-002")).toBeInTheDocument();
    expect(screen.getByText("case-003")).toBeInTheDocument();
    expect(screen.getAllByText("P0")).toHaveLength(2);
    expect(screen.getByText("P1")).toBeInTheDocument();
  });

  it("點擊案例行可展開，顯示 question 和 answer_snippet 和 assertion_results", async () => {
    const user = userEvent.setup();
    render(<CaseResultsTable caseResults={mockCaseResults} />);

    await user.click(screen.getByText("case-001"));

    expect(screen.getByText("退貨政策是什麼？")).toBeInTheDocument();
    expect(screen.getByText("您可以在 30 天內申請退貨...")).toBeInTheDocument();
    expect(screen.getByText("contains_text")).toBeInTheDocument();
    expect(screen.getByText("no_hallucination")).toBeInTheDocument();
  });

  it("P0 失敗案例應顯示紅色 P0 FAIL 標記", () => {
    render(<CaseResultsTable caseResults={mockCaseResults} />);

    expect(screen.getByText("P0 FAIL")).toBeInTheDocument();
  });

  it("API 錯誤案例（空回答 + score=0）應顯示 API 錯誤標記和警告", () => {
    const apiErrorCase: CaseResultData[] = [
      {
        case_id: "case-err",
        question: "測試問題",
        priority: "P1",
        category: "test",
        score: 0,
        passed_count: 0,
        total_count: 2,
        p0_failed: false,
        answer_snippet: "",
        assertion_results: [
          { passed: false, assertion_type: "api_error", message: "API 錯誤：timeout" },
        ],
      },
    ];
    render(<CaseResultsTable caseResults={apiErrorCase} />);

    expect(screen.getByText("API 錯誤")).toBeInTheDocument();
    expect(screen.getByText(/1\/1 個案例 API 呼叫失敗/)).toBeInTheDocument();
  });

  it("caseResults 為 undefined 時不渲染任何內容", () => {
    const { container } = render(
      <CaseResultsTable caseResults={undefined} />
    );

    expect(container.firstChild).toBeNull();
  });
});
