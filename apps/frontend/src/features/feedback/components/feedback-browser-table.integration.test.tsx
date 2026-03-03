import { describe, it, expect } from "vitest";
import { screen } from "@testing-library/react";
import { renderWithProviders } from "@/test/test-utils";
import { FeedbackBrowserTable } from "@/features/feedback/components/feedback-browser-table";
import { mockFeedbackList } from "@/test/fixtures/feedback";

describe("FeedbackBrowserTable integration", () => {
  const defaultProps = {
    data: mockFeedbackList,
    isLoading: false,
    total: 2,
    page: 0,
    onPageChange: vi.fn(),
  };

  it("should render feedback list with ratings and comments", () => {
    renderWithProviders(<FeedbackBrowserTable {...defaultProps} />);

    // Table header
    expect(screen.getByText("回饋瀏覽器")).toBeInTheDocument();
    expect(screen.getByText("時間")).toBeInTheDocument();
    expect(screen.getByText("評分")).toBeInTheDocument();

    // Feedback rows — "+" for thumbs_up, "-" for thumbs_down and null comments
    expect(screen.getByText("+")).toBeInTheDocument();
    const dashes = screen.getAllByText("-");
    expect(dashes.length).toBeGreaterThanOrEqual(1);
    // "答案不正確" appears in both comment and tag columns
    const issueTexts = screen.getAllByText("答案不正確");
    expect(issueTexts.length).toBeGreaterThanOrEqual(1);

    // Total count
    expect(screen.getByText("共 2 筆")).toBeInTheDocument();
  });

  it("should show loading skeleton when isLoading is true", () => {
    renderWithProviders(
      <FeedbackBrowserTable {...defaultProps} isLoading={true} />,
    );

    expect(screen.getByText("回饋瀏覽器")).toBeInTheDocument();
    const skeletons = document.querySelectorAll("[data-slot='skeleton']");
    expect(skeletons.length).toBeGreaterThan(0);
  });

  it("should show empty state when data is empty", () => {
    renderWithProviders(
      <FeedbackBrowserTable {...defaultProps} data={[]} total={0} />,
    );

    expect(screen.getByText("無符合條件的回饋")).toBeInTheDocument();
  });

  it("should handle pagination buttons", async () => {
    const onPageChange = vi.fn();
    renderWithProviders(
      <FeedbackBrowserTable
        {...defaultProps}
        onPageChange={onPageChange}
      />,
    );

    // Previous button should be disabled on first page
    const prevButton = screen.getByRole("button", { name: "上一頁" });
    expect(prevButton).toBeDisabled();

    // Next button disabled since total fits in one page
    const nextButton = screen.getByRole("button", { name: "下一頁" });
    expect(nextButton).toBeDisabled();
  });

  it("should render rating filter with default all value", () => {
    renderWithProviders(<FeedbackBrowserTable {...defaultProps} />);

    // The rating filter trigger shows "全部" as default
    expect(screen.getByText("全部")).toBeInTheDocument();
  });
});
