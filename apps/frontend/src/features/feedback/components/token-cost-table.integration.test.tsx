import { describe, it, expect } from "vitest";
import { screen } from "@testing-library/react";
import { renderWithProviders } from "@/test/test-utils";
import { TokenCostTable } from "@/features/feedback/components/token-cost-table";
import { mockTokenCostStats } from "@/test/fixtures/feedback";

describe("TokenCostTable integration", () => {
  it("should render cost data with model details", () => {
    renderWithProviders(
      <TokenCostTable data={mockTokenCostStats} isLoading={false} />,
    );

    // Table title
    expect(screen.getByText("Token 成本統計")).toBeInTheDocument();

    // Column headers
    expect(screen.getByText("模型")).toBeInTheDocument();
    expect(screen.getByText("訊息數")).toBeInTheDocument();
    expect(screen.getByText("預估成本")).toBeInTheDocument();

    // Model rows from mockTokenCostStats
    expect(screen.getByText("gpt-4")).toBeInTheDocument();
    expect(screen.getByText("gpt-3.5-turbo")).toBeInTheDocument();

    // Cost values
    expect(screen.getByText("$1.8500")).toBeInTheDocument();
    expect(screen.getByText("$0.1350")).toBeInTheDocument();

    // Message counts
    expect(screen.getByText("50")).toBeInTheDocument();
    expect(screen.getByText("120")).toBeInTheDocument();
  });

  it("should show loading skeleton", () => {
    renderWithProviders(
      <TokenCostTable data={undefined} isLoading={true} />,
    );

    expect(screen.getByText("Token 成本統計")).toBeInTheDocument();
    const skeletons = document.querySelectorAll("[data-slot='skeleton']");
    expect(skeletons.length).toBeGreaterThan(0);
  });

  it("should show empty state when no data", () => {
    renderWithProviders(
      <TokenCostTable data={[]} isLoading={false} />,
    );

    expect(screen.getByText("尚無成本資料")).toBeInTheDocument();
  });
});
