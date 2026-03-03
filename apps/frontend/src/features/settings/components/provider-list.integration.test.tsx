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

  it("should show pre-defined provider cards with switches", async () => {
    renderWithProviders(<ProviderList />);

    // Loading skeletons appear first
    const skeletons = document.querySelectorAll("[data-slot='skeleton']");
    expect(skeletons.length).toBeGreaterThan(0);

    // After loading, all pre-defined providers are visible
    expect(await screen.findByText("DeepSeek")).toBeInTheDocument();
    expect(screen.getByText("Anthropic Claude")).toBeInTheDocument();
    expect(screen.getByText("OpenAI")).toBeInTheDocument();
    expect(screen.getByText("Google Gemini")).toBeInTheDocument();

    // Each card has a switch for enable/disable
    const switches = screen.getAllByRole("switch");
    expect(switches.length).toBe(4); // 4 providers in PROVIDER_ORDER

    // LLM badges
    const llmBadges = screen.getAllByText("LLM");
    expect(llmBadges.length).toBe(4);
  });
});
