import { describe, expect, it, vi } from "vitest";
import { screen } from "@testing-library/react";
import { renderWithProviders } from "@/test/test-utils";
import { FeedbackBrowserTable } from "./feedback-browser-table";
import { mockFeedbackList } from "@/test/fixtures/feedback";

const noop = vi.fn();

describe("FeedbackBrowserTable", () => {
  it("renders feedback rows", () => {
    renderWithProviders(
      <FeedbackBrowserTable
        data={mockFeedbackList}
        isLoading={false}
        page={0}
        onPageChange={noop}
      />,
    );
    expect(screen.getByText("回饋瀏覽器")).toBeInTheDocument();
    expect(screen.getAllByText("答案不正確").length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText("共 2 筆")).toBeInTheDocument();
  });

  it("shows loading skeleton", () => {
    renderWithProviders(
      <FeedbackBrowserTable
        data={undefined}
        isLoading={true}
        page={0}
        onPageChange={noop}
      />,
    );
    expect(screen.getByText("回饋瀏覽器")).toBeInTheDocument();
    expect(
      document.querySelectorAll("[data-slot='skeleton']").length,
    ).toBeGreaterThan(0);
  });

  it("shows empty state when no data", () => {
    renderWithProviders(
      <FeedbackBrowserTable
        data={[]}
        isLoading={false}
        page={0}
        onPageChange={noop}
      />,
    );
    expect(screen.getByText("無符合條件的回饋")).toBeInTheDocument();
  });

  it("renders filter selector", () => {
    renderWithProviders(
      <FeedbackBrowserTable
        data={mockFeedbackList}
        isLoading={false}
        page={0}
        onPageChange={noop}
      />,
    );
    // Filter trigger (combobox) should be present
    expect(screen.getByRole("combobox")).toBeInTheDocument();
  });

  it("handles pagination buttons", () => {
    renderWithProviders(
      <FeedbackBrowserTable
        data={mockFeedbackList}
        isLoading={false}
        page={0}
        onPageChange={noop}
      />,
    );
    expect(screen.getByRole("button", { name: "上一頁" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "下一頁" })).toBeDisabled();
  });
});
