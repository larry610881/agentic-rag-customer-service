import { describe, it, expect, beforeEach } from "vitest";
import { screen } from "@testing-library/react";
import { renderWithProviders } from "@/test/test-utils";
import { ProviderList } from "@/features/settings/components/provider-list";
import { useAuthStore } from "@/stores/use-auth-store";

describe("ProviderList integration", () => {
  beforeEach(() => {
    useAuthStore.setState({
      token: "test-token",
      tenantId: "tenant-1",
      tenants: [],
    });
  });

  it("should fetch and display providers from MSW", async () => {
    renderWithProviders(<ProviderList />);

    // Loading skeletons appear first
    const skeletons = document.querySelectorAll("[data-slot='skeleton']");
    expect(skeletons.length).toBeGreaterThan(0);

    // After loading, display provider data
    expect(
      await screen.findByText("OpenAI GPT-4o"),
    ).toBeInTheDocument();
    expect(screen.getByText("OpenAI Embedding")).toBeInTheDocument();

    // Should show provider type badges
    expect(screen.getByText("llm")).toBeInTheDocument();
    expect(screen.getByText("embedding")).toBeInTheDocument();

    // Should show .env managed hint
    const envTexts = screen.getAllByText("API Key 由 .env 管理");
    expect(envTexts.length).toBe(2);

    // Should show action buttons for each provider
    const editButtons = screen.getAllByRole("button", { name: "編輯" });
    expect(editButtons.length).toBe(2);
  });

  it("should filter providers by type when type prop is set", async () => {
    renderWithProviders(<ProviderList type="llm" />);

    // After loading, should show filtered provider
    expect(
      await screen.findByText("OpenAI GPT-4o"),
    ).toBeInTheDocument();

    // Should display "LLM" in the heading (text may include whitespace)
    expect(screen.getByText(/LLM/)).toBeInTheDocument();
  });
});
