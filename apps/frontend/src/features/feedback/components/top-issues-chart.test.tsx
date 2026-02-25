import { describe, expect, it } from "vitest";
import { screen } from "@testing-library/react";
import { renderWithProviders } from "@/test/test-utils";
import { TopIssuesChart } from "./top-issues-chart";
import { mockTopIssues } from "@/test/fixtures/feedback";

describe("TopIssuesChart", () => {
  it("renders chart title", () => {
    renderWithProviders(
      <TopIssuesChart data={mockTopIssues} isLoading={false} />,
    );
    expect(screen.getByText("常見問題標籤")).toBeInTheDocument();
  });

  it("shows loading skeleton", () => {
    renderWithProviders(
      <TopIssuesChart data={undefined} isLoading={true} />,
    );
    expect(screen.getByText("常見問題標籤")).toBeInTheDocument();
    expect(
      document.querySelectorAll("[data-slot='skeleton']").length,
    ).toBeGreaterThan(0);
  });

  it("shows empty state when no data", () => {
    renderWithProviders(
      <TopIssuesChart data={[]} isLoading={false} />,
    );
    expect(screen.getByText("尚無問題標籤")).toBeInTheDocument();
  });
});
