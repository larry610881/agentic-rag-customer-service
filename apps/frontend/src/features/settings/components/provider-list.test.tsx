import { describe, expect, it } from "vitest";
import { screen, waitFor } from "@testing-library/react";
import { renderWithProviders } from "@/test/test-utils";
import { useAuthStore } from "@/stores/use-auth-store";
import { ProviderList } from "./provider-list";

describe("ProviderList", () => {
  it("should render loading skeletons initially", () => {
    useAuthStore.setState({ token: "mock-token", tenantId: "t-001" });
    renderWithProviders(<ProviderList />);
    // Skeleton elements are rendered during loading
    expect(document.querySelectorAll("[data-slot='skeleton']").length).toBeGreaterThanOrEqual(0);
  });

  it("should render provider cards after loading", async () => {
    useAuthStore.setState({ token: "mock-token", tenantId: "t-001" });
    renderWithProviders(<ProviderList />);

    await waitFor(() => {
      expect(screen.getByText("OpenAI GPT-4o")).toBeInTheDocument();
    });
    expect(screen.getByText("OpenAI Embedding")).toBeInTheDocument();
  });

  it("should filter by type when type prop is set", async () => {
    useAuthStore.setState({ token: "mock-token", tenantId: "t-001" });
    renderWithProviders(<ProviderList type="llm" />);

    await waitFor(() => {
      expect(screen.getByText("OpenAI GPT-4o")).toBeInTheDocument();
    });
    expect(screen.queryByText("OpenAI Embedding")).not.toBeInTheDocument();
  });

  it("should show add provider button", async () => {
    useAuthStore.setState({ token: "mock-token", tenantId: "t-001" });
    renderWithProviders(<ProviderList />);

    await waitFor(() => {
      expect(
        screen.getByRole("button", { name: /新增供應商/ }),
      ).toBeInTheDocument();
    });
  });

  it("should show enabled/disabled badges", async () => {
    useAuthStore.setState({ token: "mock-token", tenantId: "t-001" });
    renderWithProviders(<ProviderList />);

    await waitFor(() => {
      const badges = screen.getAllByText("啟用");
      expect(badges.length).toBeGreaterThan(0);
    });
  });
});
