import { describe, expect, it, vi } from "vitest";
import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { renderWithProviders } from "@/test/test-utils";
import { DocumentList } from "./document-list";
import { mockDocuments } from "@/test/fixtures/knowledge";
import type { DocumentResponse } from "@/types/knowledge";

describe("DocumentList", () => {
  it("renders empty state when no documents", () => {
    renderWithProviders(<DocumentList kbId="kb-1" documents={[]} />);
    expect(screen.getByText("尚未上傳任何文件。")).toBeInTheDocument();
  });

  it("renders document rows", () => {
    renderWithProviders(<DocumentList kbId="kb-1" documents={mockDocuments} />);
    expect(screen.getByText("product-guide.pdf")).toBeInTheDocument();
    expect(screen.getByText("setup-manual.pdf")).toBeInTheDocument();
  });

  it("displays chunk count for each document", () => {
    renderWithProviders(<DocumentList kbId="kb-1" documents={mockDocuments} />);
    expect(screen.getByText("42")).toBeInTheDocument();
  });

  it("displays status icon with Chinese text for processed", () => {
    const docs: DocumentResponse[] = [
      { ...mockDocuments[0], status: "processed" },
    ];
    renderWithProviders(<DocumentList kbId="kb-1" documents={docs} />);
    expect(screen.getByText("完成")).toBeInTheDocument();
  });

  it("displays status icon with Chinese text for processing", () => {
    const docs: DocumentResponse[] = [
      { ...mockDocuments[0], status: "processing" },
    ];
    renderWithProviders(<DocumentList kbId="kb-1" documents={docs} />);
    expect(screen.getByText("學習中")).toBeInTheDocument();
  });

  it("displays status icon with Chinese text for pending", () => {
    const docs: DocumentResponse[] = [
      { ...mockDocuments[0], status: "pending" },
    ];
    renderWithProviders(<DocumentList kbId="kb-1" documents={docs} />);
    expect(screen.getByText("等待中")).toBeInTheDocument();
  });

  it("displays status icon with Chinese text for failed", () => {
    const docs: DocumentResponse[] = [
      { ...mockDocuments[0], status: "failed" },
    ];
    renderWithProviders(<DocumentList kbId="kb-1" documents={docs} />);
    expect(screen.getByText("失敗")).toBeInTheDocument();
  });

  it("shows delete buttons when onDelete is provided", () => {
    const onDelete = vi.fn();
    renderWithProviders(<DocumentList kbId="kb-1" documents={mockDocuments} onDelete={onDelete} />);
    const deleteButtons = screen.getAllByRole("button", { name: "刪除" });
    expect(deleteButtons).toHaveLength(2);
  });

  it("does not show delete buttons when onDelete is not provided", () => {
    renderWithProviders(<DocumentList kbId="kb-1" documents={mockDocuments} />);
    expect(screen.queryByRole("button", { name: "刪除" })).not.toBeInTheDocument();
  });

  it("opens confirmation dialog on delete click", async () => {
    const user = userEvent.setup();
    const onDelete = vi.fn();
    renderWithProviders(<DocumentList kbId="kb-1" documents={mockDocuments} onDelete={onDelete} />);

    const deleteButtons = screen.getAllByRole("button", { name: "刪除" });
    await user.click(deleteButtons[0]);

    expect(screen.getByText("刪除文件")).toBeInTheDocument();
    expect(screen.getByRole("alertdialog")).toHaveTextContent("product-guide.pdf");
  });

  it("calls onDelete when confirmed", async () => {
    const user = userEvent.setup();
    const onDelete = vi.fn();
    renderWithProviders(<DocumentList kbId="kb-1" documents={mockDocuments} onDelete={onDelete} />);

    const deleteButtons = screen.getAllByRole("button", { name: "刪除" });
    await user.click(deleteButtons[0]);

    const dialog = screen.getByRole("alertdialog");
    const confirmButton = within(dialog).getByRole("button", { name: "刪除" });
    await user.click(confirmButton);

    expect(onDelete).toHaveBeenCalledWith("doc-1");
  });

  it("does not call onDelete when cancelled", async () => {
    const user = userEvent.setup();
    const onDelete = vi.fn();
    renderWithProviders(<DocumentList kbId="kb-1" documents={mockDocuments} onDelete={onDelete} />);

    const deleteButtons = screen.getAllByRole("button", { name: "刪除" });
    await user.click(deleteButtons[0]);

    const cancelButton = screen.getByRole("button", { name: "取消" });
    await user.click(cancelButton);

    expect(onDelete).not.toHaveBeenCalled();
  });

  it("shows green quality icon for score >= 0.8", () => {
    const docs: DocumentResponse[] = [
      { ...mockDocuments[0], status: "processed", quality_score: 0.9, quality_issues: [] },
    ];
    renderWithProviders(<DocumentList kbId="kb-1" documents={docs} />);
    expect(screen.getByTestId("quality-good")).toBeInTheDocument();
  });

  it("shows yellow quality icon for score >= 0.5", () => {
    const docs: DocumentResponse[] = [
      { ...mockDocuments[0], status: "processed", quality_score: 0.6, quality_issues: ["too_short"] },
    ];
    renderWithProviders(<DocumentList kbId="kb-1" documents={docs} />);
    expect(screen.getByTestId("quality-warning")).toBeInTheDocument();
  });

  it("shows red quality icon for score < 0.5", () => {
    const docs: DocumentResponse[] = [
      { ...mockDocuments[0], status: "processed", quality_score: 0.3, quality_issues: ["too_short", "high_variance"] },
    ];
    renderWithProviders(<DocumentList kbId="kb-1" documents={docs} />);
    expect(screen.getByTestId("quality-poor")).toBeInTheDocument();
  });

  it("does not show quality icon for non-processed documents", () => {
    const docs: DocumentResponse[] = [
      { ...mockDocuments[0], status: "processing", quality_score: 0.0 },
    ];
    renderWithProviders(<DocumentList kbId="kb-1" documents={docs} />);
    expect(screen.queryByTestId("quality-good")).not.toBeInTheDocument();
    expect(screen.queryByTestId("quality-warning")).not.toBeInTheDocument();
    expect(screen.queryByTestId("quality-poor")).not.toBeInTheDocument();
  });

  it("shows negative feedback badge when qualityStats provided", () => {
    const stats = [
      { document_id: "doc-1", filename: "product-guide.pdf", quality_score: 0.9, negative_feedback_count: 3 },
    ];
    renderWithProviders(
      <DocumentList kbId="kb-1" documents={mockDocuments} qualityStats={stats} />
    );
    expect(screen.getByTestId("negative-feedback-badge")).toHaveTextContent("3 差評");
  });
});
