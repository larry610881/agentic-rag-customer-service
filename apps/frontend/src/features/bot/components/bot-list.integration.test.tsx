import { describe, it, expect, beforeEach } from "vitest";
import { screen } from "@testing-library/react";
import { renderWithProviders } from "@/test/test-utils";
import { BotList } from "@/features/bot/components/bot-list";
import { useAuthStore } from "@/stores/use-auth-store";

describe("BotList integration", () => {
  beforeEach(() => {
    useAuthStore.setState({
      token: "test-token",
      tenantId: "tenant-1",
      tenants: [],
    });
  });

  it("should fetch and display bots from MSW", async () => {
    renderWithProviders(<BotList />);

    // Loading skeleton should appear first
    const skeletons = document.querySelectorAll("[data-slot='skeleton']");
    expect(skeletons.length).toBeGreaterThan(0);

    // After loading, should display bot data from MSW handlers
    expect(
      await screen.findByText("Customer Service Bot"),
    ).toBeInTheDocument();
    expect(screen.getByText("FAQ Bot")).toBeInTheDocument();

    // Should display active/inactive badges
    expect(screen.getByText("啟用")).toBeInTheDocument();
    expect(screen.getByText("停用")).toBeInTheDocument();

    // Should display KB count badges
    expect(screen.getByText("2 KB")).toBeInTheDocument();
    expect(screen.getByText("1 KB")).toBeInTheDocument();
  });
});
