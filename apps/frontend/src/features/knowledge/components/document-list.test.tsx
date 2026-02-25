import { describe, expect, it, vi } from "vitest";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { DocumentList } from "./document-list";
import { mockDocuments } from "@/test/fixtures/knowledge";

describe("DocumentList", () => {
  it("renders empty state when no documents", () => {
    render(<DocumentList documents={[]} />);
    expect(screen.getByText("尚未上傳任何文件。")).toBeInTheDocument();
  });

  it("renders document rows", () => {
    render(<DocumentList documents={mockDocuments} />);
    expect(screen.getByText("product-guide.pdf")).toBeInTheDocument();
    expect(screen.getByText("setup-manual.pdf")).toBeInTheDocument();
  });

  it("displays chunk count for each document", () => {
    render(<DocumentList documents={mockDocuments} />);
    expect(screen.getByText("42")).toBeInTheDocument();
  });

  it("displays status badges", () => {
    render(<DocumentList documents={mockDocuments} />);
    expect(screen.getByText("processed")).toBeInTheDocument();
    expect(screen.getByText("processing")).toBeInTheDocument();
  });

  it("shows delete buttons when onDelete is provided", () => {
    const onDelete = vi.fn();
    render(<DocumentList documents={mockDocuments} onDelete={onDelete} />);
    const deleteButtons = screen.getAllByRole("button", { name: "刪除" });
    expect(deleteButtons).toHaveLength(2);
  });

  it("does not show delete buttons when onDelete is not provided", () => {
    render(<DocumentList documents={mockDocuments} />);
    expect(screen.queryByRole("button", { name: "刪除" })).not.toBeInTheDocument();
  });

  it("opens confirmation dialog on delete click", async () => {
    const user = userEvent.setup();
    const onDelete = vi.fn();
    render(<DocumentList documents={mockDocuments} onDelete={onDelete} />);

    const deleteButtons = screen.getAllByRole("button", { name: "刪除" });
    await user.click(deleteButtons[0]);

    expect(screen.getByText("刪除文件")).toBeInTheDocument();
    expect(screen.getByRole("alertdialog")).toHaveTextContent("product-guide.pdf");
  });

  it("calls onDelete when confirmed", async () => {
    const user = userEvent.setup();
    const onDelete = vi.fn();
    render(<DocumentList documents={mockDocuments} onDelete={onDelete} />);

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
    render(<DocumentList documents={mockDocuments} onDelete={onDelete} />);

    const deleteButtons = screen.getAllByRole("button", { name: "刪除" });
    await user.click(deleteButtons[0]);

    const cancelButton = screen.getByRole("button", { name: "取消" });
    await user.click(cancelButton);

    expect(onDelete).not.toHaveBeenCalled();
  });
});
