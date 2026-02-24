import { describe, it, expect, beforeEach } from "vitest";
import { screen } from "@testing-library/react";
import { renderWithProviders } from "@/test/test-utils";
import { BotList } from "@/features/bot/components/bot-list";
import { useAuthStore } from "@/stores/use-auth-store";

describe("BotList", () => {
  beforeEach(() => {
    useAuthStore.setState({
      token: "test-token",
      tenantId: "tenant-1",
      tenants: [],
    });
  });

  it("should show loading skeletons initially", () => {
    renderWithProviders(<BotList />);
    const skeletons = document.querySelectorAll("[data-slot='skeleton']");
    expect(skeletons.length).toBeGreaterThan(0);
  });

  it("should render bot cards after loading", async () => {
    renderWithProviders(<BotList />);
    expect(
      await screen.findByText("Customer Service Bot"),
    ).toBeInTheDocument();
    expect(screen.getByText("FAQ Bot")).toBeInTheDocument();
  });

  it("should display active/inactive badges", async () => {
    renderWithProviders(<BotList />);
    await screen.findByText("Customer Service Bot");
    expect(screen.getByText("Active")).toBeInTheDocument();
    expect(screen.getByText("Inactive")).toBeInTheDocument();
  });
});
