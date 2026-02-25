import { describe, expect, it, vi } from "vitest";
import { screen } from "@testing-library/react";
import { renderWithProviders, userEvent } from "@/test/test-utils";
import { TagEditor } from "./tag-editor";

describe("TagEditor", () => {
  it("renders existing tags", () => {
    renderWithProviders(
      <TagEditor tags={["答案不正確", "不完整"]} onSave={vi.fn()} />,
    );
    expect(screen.getByText("答案不正確")).toBeInTheDocument();
    expect(screen.getByText("不完整")).toBeInTheDocument();
  });

  it("adds a new tag via input + Enter", async () => {
    const user = userEvent.setup();
    renderWithProviders(
      <TagEditor tags={[]} onSave={vi.fn()} />,
    );

    await user.type(screen.getByPlaceholderText("新增標籤..."), "新標籤{enter}");
    expect(screen.getByText("新標籤")).toBeInTheDocument();
  });

  it("removes a tag", async () => {
    const user = userEvent.setup();
    renderWithProviders(
      <TagEditor tags={["答案不正確"]} onSave={vi.fn()} />,
    );

    await user.click(screen.getByLabelText("移除標籤 答案不正確"));
    expect(screen.queryByText("答案不正確")).not.toBeInTheDocument();
  });

  it("calls onSave with updated tags", async () => {
    const onSave = vi.fn();
    const user = userEvent.setup();
    renderWithProviders(
      <TagEditor tags={["原有"]} onSave={onSave} />,
    );

    // Add a new tag
    await user.type(screen.getByPlaceholderText("新增標籤..."), "新增{enter}");
    // Save button should appear
    await user.click(screen.getByRole("button", { name: "儲存標籤" }));
    expect(onSave).toHaveBeenCalledWith(["原有", "新增"]);
  });

  it("does not show save button when no changes", () => {
    renderWithProviders(
      <TagEditor tags={["tag1"]} onSave={vi.fn()} />,
    );
    expect(screen.queryByRole("button", { name: "儲存標籤" })).not.toBeInTheDocument();
  });
});
