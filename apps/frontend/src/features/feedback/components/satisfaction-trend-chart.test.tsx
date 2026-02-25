import { describe, expect, it } from "vitest";
import { screen } from "@testing-library/react";
import { renderWithProviders } from "@/test/test-utils";
import { SatisfactionTrendChart } from "./satisfaction-trend-chart";
import { mockSatisfactionTrend } from "@/test/fixtures/feedback";

describe("SatisfactionTrendChart", () => {
  it("renders chart title", () => {
    renderWithProviders(
      <SatisfactionTrendChart data={mockSatisfactionTrend} isLoading={false} />,
    );
    expect(screen.getByText("滿意度趨勢")).toBeInTheDocument();
  });

  it("shows loading skeleton", () => {
    renderWithProviders(
      <SatisfactionTrendChart data={undefined} isLoading={true} />,
    );
    expect(screen.getByText("滿意度趨勢")).toBeInTheDocument();
    expect(
      document.querySelectorAll("[data-slot='skeleton']").length,
    ).toBeGreaterThan(0);
  });

  it("shows empty state when no data", () => {
    renderWithProviders(
      <SatisfactionTrendChart data={[]} isLoading={false} />,
    );
    expect(screen.getByText("尚無趨勢資料")).toBeInTheDocument();
  });
});
