import { describe, it, expect } from "vitest";
import { screen } from "@testing-library/react";
import { renderWithProviders } from "@/test/test-utils";
import { FeedbackStatsSummary } from "@/features/feedback/components/feedback-stats-summary";
import { mockFeedbackStats } from "@/test/fixtures/feedback";

describe("FeedbackStatsSummary integration", () => {
  it("should render all stat cards with correct values", () => {
    renderWithProviders(
      <FeedbackStatsSummary stats={mockFeedbackStats} isLoading={false} />,
    );

    // Card titles
    expect(screen.getByText("總回饋數")).toBeInTheDocument();
    expect(screen.getByText("正面回饋")).toBeInTheDocument();
    expect(screen.getByText("負面回饋")).toBeInTheDocument();
    expect(screen.getByText("滿意度")).toBeInTheDocument();

    // Values from mockFeedbackStats: total=10, thumbs_up=7, thumbs_down=3, satisfaction_rate=70.0
    expect(screen.getByText("10")).toBeInTheDocument();
    expect(screen.getByText("7")).toBeInTheDocument();
    expect(screen.getByText("3")).toBeInTheDocument();
    expect(screen.getByText("70.0%")).toBeInTheDocument();
  });

  it("should show loading skeletons when isLoading is true", () => {
    renderWithProviders(
      <FeedbackStatsSummary stats={undefined} isLoading={true} />,
    );

    const skeletons = document.querySelectorAll("[data-slot='skeleton']");
    expect(skeletons.length).toBeGreaterThan(0);
  });

  it("should show zero values when stats are undefined", () => {
    renderWithProviders(
      <FeedbackStatsSummary stats={undefined} isLoading={false} />,
    );

    // All values should show 0
    const zeros = screen.getAllByText("0");
    expect(zeros.length).toBe(3);
    expect(screen.getByText("0.0%")).toBeInTheDocument();
  });
});
