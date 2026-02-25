import { describe, it, expect, beforeEach } from "vitest";
import { screen } from "@testing-library/react";
import { renderWithProviders } from "@/test/test-utils";
import { KnowledgeBaseList } from "@/features/knowledge/components/knowledge-base-list";
import { useAuthStore } from "@/stores/use-auth-store";

describe("KnowledgeBaseList integration", () => {
  beforeEach(() => {
    useAuthStore.setState({
      token: "test-token",
      tenantId: "tenant-1",
      tenants: [],
    });
  });

  it("should fetch and display knowledge bases from MSW", async () => {
    renderWithProviders(<KnowledgeBaseList />);

    // 應先顯示載入狀態（骨架屏）
    const skeletons = document.querySelectorAll("[data-slot='skeleton']");
    expect(skeletons.length).toBeGreaterThan(0);

    // 載入完成後，應顯示來自 MSW handler 的知識庫資料
    expect(
      await screen.findByText("Product Documentation"),
    ).toBeInTheDocument();
    expect(screen.getByText("FAQ")).toBeInTheDocument();
    expect(screen.getByText("5 份文件")).toBeInTheDocument();
    expect(screen.getByText("3 份文件")).toBeInTheDocument();
    expect(
      screen.getByText("All product-related documents"),
    ).toBeInTheDocument();
  });
});
