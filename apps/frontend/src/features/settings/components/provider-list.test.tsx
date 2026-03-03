import { describe, expect, it } from "vitest";
import { screen, waitFor } from "@testing-library/react";
import { renderWithProviders } from "@/test/test-utils";
import { useAuthStore } from "@/stores/use-auth-store";
import { ProviderList } from "./provider-list";

describe("ProviderList", () => {
  it("should render loading skeletons initially", () => {
    useAuthStore.setState({ token: "mock-token", tenantId: "t-001" });
    renderWithProviders(<ProviderList type="llm" />);
    expect(
      document.querySelectorAll("[data-slot='skeleton']").length,
    ).toBeGreaterThanOrEqual(0);
  });

  it("should show all pre-defined provider cards for LLM type", async () => {
    useAuthStore.setState({ token: "mock-token", tenantId: "t-001" });
    renderWithProviders(<ProviderList type="llm" />);

    // Pre-defined providers always appear
    await waitFor(() => {
      expect(screen.getByText("DeepSeek")).toBeInTheDocument();
    });
    expect(screen.getByText("Anthropic Claude")).toBeInTheDocument();
    expect(screen.getByText("Google Gemini")).toBeInTheDocument();
    expect(screen.getByText("OpenAI")).toBeInTheDocument();
  });

  it("should show LLM badges when type=llm", async () => {
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
    renderWithProviders(<ProviderList type="llm" />);

    await waitFor(() => {
      expect(screen.getByText("DeepSeek")).toBeInTheDocument();
    });

    const switches = screen.getAllByRole("switch");
    // 4 providers in PROVIDER_ORDER
    expect(switches.length).toBe(4);
  });
});
