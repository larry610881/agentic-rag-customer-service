import { describe, it, expect } from "vitest";
import { screen } from "@testing-library/react";
import { renderWithProviders } from "@/test/test-utils";
import { CitationList } from "@/features/chat/components/citation-list";
import { mockSources } from "@/test/fixtures/chat";

describe("CitationList", () => {
  it("should render nothing when sources is empty", () => {
    const { container } = renderWithProviders(<CitationList sources={[]} />);
    expect(container.firstChild).toBeNull();
  });

  it("should render source cards", () => {
    renderWithProviders(<CitationList sources={mockSources} />);
    expect(screen.getByText("參考來源")).toBeInTheDocument();
    expect(screen.getByText("product-guide.pdf")).toBeInTheDocument();
    expect(screen.getByText("faq.pdf")).toBeInTheDocument();
  });

  it("should display relevance scores", () => {
    renderWithProviders(<CitationList sources={mockSources} />);
    expect(screen.getByText("95%")).toBeInTheDocument();
    expect(screen.getByText("87%")).toBeInTheDocument();
  });
});
