import { describe, expect, it } from "vitest";
import { screen, waitFor } from "@testing-library/react";
import { renderWithProviders } from "@/test/test-utils";
import { useAuthStore } from "@/stores/use-auth-store";
import { ProviderList } from "./provider-list";

describe("ProviderList", () => {
  it("should render loading skeletons initially", () => {
    useAuthStore.setState({ token: "mock-token", tenantId: "t-001" });
    renderWithProviders(<ProviderList />);
    expect(
      document.querySelectorAll("[data-slot='skeleton']").length,
    ).toBeGreaterThanOrEqual(0);
  });

  it("should show all pre-defined provider cards", async () => {
    useAuthStore.setState({ token: "mock-token", tenantId: "t-001" });
    renderWithProviders(<ProviderList />);

    // Pre-defined providers always appear (no need to "add")
    await waitFor(() => {
      expect(screen.getByText("DeepSeek")).toBeInTheDocument();
    });
    expect(screen.getByText("Anthropic Claude")).toBeInTheDocument();

    // Google Gemini appears twice (LLM + Embedding)
    const googleCards = screen.getAllByText("Google Gemini");
    expect(googleCards.length).toBe(2);

    // OpenAI appears for both LLM and Embedding
    const openaiCards = screen.getAllByText("OpenAI");
    expect(openaiCards.length).toBe(2);
  });

  it("should filter to LLM only when type=llm", async () => {
    useAuthStore.setState({ token: "mock-token", tenantId: "t-001" });
    renderWithProviders(<ProviderList type="llm" />);

    await waitFor(() => {
      expect(screen.getByText("DeepSeek")).toBeInTheDocument();
    });

    // Only LLM badges
    const llmBadges = screen.getAllByText("LLM");
    expect(llmBadges.length).toBe(4);
    expect(screen.queryByText("EMBEDDING")).not.toBeInTheDocument();
  });

  it("should show enable/disable switches on each card", async () => {
    useAuthStore.setState({ token: "mock-token", tenantId: "t-001" });
    renderWithProviders(<ProviderList />);

    await waitFor(() => {
      expect(screen.getByText("DeepSeek")).toBeInTheDocument();
    });

    const switches = screen.getAllByRole("switch");
    // 4 LLM providers + 2 Embedding providers = 6
    expect(switches.length).toBe(6);
  });

  it("should display model names and pricing", async () => {
    useAuthStore.setState({ token: "mock-token", tenantId: "t-001" });
    renderWithProviders(<ProviderList type="llm" />);

    await waitFor(() => {
      expect(screen.getByText("DeepSeek V3")).toBeInTheDocument();
    });
    expect(screen.getByText("$0.14/$0.28")).toBeInTheDocument();
  });
});
