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
    expect(deleteButtons).toHaveLength(3);
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

  // --- StatusCell 階段切換（catalog PDF 父文件）regression ---

  function makeCatalogParent(overrides: Partial<DocumentResponse> = {}): DocumentResponse {
    return {
      id: "parent-1",
      kb_id: "kb-1",
      tenant_id: "tenant-1",
      filename: "catalog.pdf",
      content_type: "application/pdf",
      status: "processing",
      chunk_count: 0,
      avg_chunk_length: 0,
      min_chunk_length: 0,
      max_chunk_length: 0,
      quality_score: 0,
      quality_issues: [],
      has_file: true,
      task_progress: null,
      parent_id: null,
      page_number: null,
      children_count: 8,
      completed_children_count: 0,
      created_at: "2026-04-16T00:00:00Z",
      updated_at: "2026-04-16T00:00:00Z",
      ...overrides,
    };
  }

  it("OCR 階段：父文件 task_progress 未達 100 時顯示百分比", () => {
    const doc = makeCatalogParent({
      task_progress: 15,
      children_count: 8,
      completed_children_count: 0,
    });
    renderWithProviders(<DocumentList kbId="kb-1" documents={[doc]} />);
    expect(screen.getByText(/學習中\s*15%/)).toBeInTheDocument();
    expect(screen.queryByText(/張/)).not.toBeInTheDocument();
  });

  it("子頁階段：父 task 已完成時顯示「完成 N / 總 M 張」", () => {
    const doc = makeCatalogParent({
      task_progress: null,
      children_count: 8,
      completed_children_count: 3,
    });
    renderWithProviders(<DocumentList kbId="kb-1" documents={[doc]} />);
    expect(screen.getByText("學習中 3/8 張")).toBeInTheDocument();
    expect(screen.queryByText(/15%/)).not.toBeInTheDocument();
  });

  it("非 catalog 一般文件 processing 時保留百分比顯示（回歸）", () => {
    const doc: DocumentResponse = {
      ...mockDocuments[0],
      status: "processing",
      task_progress: 50,
      children_count: 0,
      completed_children_count: 0,
    };
    renderWithProviders(<DocumentList kbId="kb-1" documents={[doc]} />);
    expect(screen.getByText(/學習中\s*50%/)).toBeInTheDocument();
  });

  it("processing 時不顯示 ParentPageProgress summary「頁」避免與 StatusCell 重複", () => {
    const doc = makeCatalogParent({
      status: "processing",
      children_count: 8,
      completed_children_count: 3,
    });
    renderWithProviders(<DocumentList kbId="kb-1" documents={[doc]} />);
    // 檔名旁不應出現「頁」summary（它會走 StatusCell 的 "3/8 張"）
    expect(screen.queryByText(/\d+\s*頁/)).not.toBeInTheDocument();
  });

  it("processed 時 ParentPageProgress 顯示 summary 總頁數", () => {
    const doc = makeCatalogParent({
      status: "processed",
      children_count: 8,
      completed_children_count: 8,
      task_progress: null,
    });
    renderWithProviders(<DocumentList kbId="kb-1" documents={[doc]} />);
    // ParentPageProgress 初始無 children query 資料時顯示 "(N 頁)"
    // 即使 useQuery 拉到資料也會顯示 "(8 頁)"（全部 processed）
    // waitFor 以保險
    expect(screen.getByText(/8\s*頁/)).toBeInTheDocument();
  });
});
