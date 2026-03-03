import { describe, it, expect } from "vitest";
import { screen } from "@testing-library/react";
import { renderWithProviders, userEvent } from "@/test/test-utils";
import { DocumentList } from "@/features/knowledge/components/document-list";
import { mockDocuments } from "@/test/fixtures/knowledge";

describe("DocumentList integration", () => {
  const defaultProps = {
    kbId: "kb-1",
    documents: mockDocuments,
    onDelete: vi.fn(),
    isDeleting: false,
  };

  it("should render documents with status and quality indicators", () => {
    renderWithProviders(<DocumentList {...defaultProps} />);

    // Document filenames
    expect(screen.getByText("product-guide.pdf")).toBeInTheDocument();
    expect(screen.getByText("setup-manual.pdf")).toBeInTheDocument();

    // Status indicators
    expect(screen.getByText("完成")).toBeInTheDocument();
    expect(screen.getByText("學習中")).toBeInTheDocument();

    // Chunk count
    expect(screen.getByText("42")).toBeInTheDocument();

    // Quality score for processed document (0.9)
    expect(screen.getByTestId("quality-good")).toBeInTheDocument();
    expect(screen.getByText("0.9")).toBeInTheDocument();
  });

  it("should show empty state when no documents", () => {
    renderWithProviders(
      <DocumentList {...defaultProps} documents={[]} />,
    );

    expect(screen.getByText("尚未上傳任何文件。")).toBeInTheDocument();
  });

  it("should show delete confirmation dialog when clicking delete", async () => {
    const user = userEvent.setup();
    renderWithProviders(<DocumentList {...defaultProps} />);

    // Click the first delete button
    const deleteButtons = screen.getAllByRole("button", { name: "刪除" });
    await user.click(deleteButtons[0]);

    // Confirmation dialog should appear
    expect(
      await screen.findByText(/確定要刪除「product-guide.pdf」嗎/),
    ).toBeInTheDocument();
    expect(screen.getByText("取消")).toBeInTheDocument();
  });

  it("should show reprocess button for processed documents and retry for failed", () => {
    renderWithProviders(<DocumentList {...defaultProps} />);

    // "重新處理" for processed doc
    const reprocessButtons = screen.getAllByRole("button", {
      name: "重新處理",
    });
    expect(reprocessButtons.length).toBe(1);

    // "重試" for failed doc
    const retryButtons = screen.getAllByRole("button", {
      name: "重試",
    });
    expect(retryButtons.length).toBe(1);
  });
});
