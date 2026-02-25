import { describe, it, expect, beforeEach } from "vitest";
import { screen } from "@testing-library/react";
import { renderWithProviders } from "@/test/test-utils";
import { KnowledgeBaseList } from "@/features/knowledge/components/knowledge-base-list";
import { useAuthStore } from "@/stores/use-auth-store";

describe("KnowledgeBaseList", () => {
  beforeEach(() => {
    useAuthStore.setState({
      token: "test-token",
      tenantId: "tenant-1",
      tenants: [],
    });
  });

  it("should show loading skeletons initially", () => {
    renderWithProviders(<KnowledgeBaseList />);
    // Skeletons should be present during loading
    const skeletons = document.querySelectorAll("[data-slot='skeleton']");
    expect(skeletons.length).toBeGreaterThan(0);
  });

  it("should render knowledge base cards after loading", async () => {
    renderWithProviders(<KnowledgeBaseList />);
    expect(
      await screen.findByText("Product Documentation"),
    ).toBeInTheDocument();
    expect(screen.getByText("FAQ")).toBeInTheDocument();
  });

  it("should display document counts", async () => {
    renderWithProviders(<KnowledgeBaseList />);
    await screen.findByText("Product Documentation");
    expect(screen.getByText("5 份文件")).toBeInTheDocument();
    expect(screen.getByText("3 份文件")).toBeInTheDocument();
  });
});
