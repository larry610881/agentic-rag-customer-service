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

    // OpenAI appears twice (LLM + Embedding)
    const openaiCards = screen.getAllByText("OpenAI");
    expect(openaiCards.length).toBe(2);

    // Each card has a switch for enable/disable
    const switches = screen.getAllByRole("switch");
    expect(switches.length).toBeGreaterThanOrEqual(6); // 4 LLM + 2 Embedding

    // LLM and Embedding badges
    const llmBadges = screen.getAllByText("LLM");
    expect(llmBadges.length).toBe(4);
    const embeddingBadges = screen.getAllByText("EMBEDDING");
    expect(embeddingBadges.length).toBe(2);
  });

  it("should filter to LLM cards only", async () => {
    renderWithProviders(<ProviderList type="llm" />);

    expect(await screen.findByText("DeepSeek")).toBeInTheDocument();

    // Only LLM badges, no EMBEDDING
    const llmBadges = screen.getAllByText("LLM");
    expect(llmBadges.length).toBe(4);
    expect(screen.queryByText("EMBEDDING")).not.toBeInTheDocument();
  });

  it("should show model names and pricing", async () => {
    renderWithProviders(<ProviderList type="llm" />);

    // Wait for render
    await screen.findByText("DeepSeek");

    // DeepSeek models
    expect(screen.getByText("DeepSeek V3")).toBeInTheDocument();
    expect(screen.getByText("$0.14/$0.28")).toBeInTheDocument();

    // OpenAI models
    expect(screen.getByText("GPT-4o")).toBeInTheDocument();
  });
});
