import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ReprocessDialog } from "./reprocess-dialog";
import type { KnowledgeBase } from "@/types/knowledge";

const baseKb: KnowledgeBase = {
  id: "kb-1",
  tenant_id: "t-1",
  name: "Test KB",
  description: "",
  ocr_mode: "catalog",
  ocr_model: "anthropic:claude-sonnet-4-6",
  context_model: "anthropic:claude-haiku-4-5",
  classification_model: "",
  chunk_strategy: "separator",
  dm_metadata_model: "",
  document_count: 0,
  created_at: "2026-05-01T00:00:00Z",
  updated_at: "2026-05-01T00:00:00Z",
};

const setup = (overrides: Partial<Parameters<typeof ReprocessDialog>[0]> = {}) => {
  const onConfirm = vi.fn();
  const onOpenChange = vi.fn();
  render(
    <ReprocessDialog
      open
      onOpenChange={onOpenChange}
      onConfirm={onConfirm}
      filename="test.pdf"
      kbDefaults={baseKb}
      {...overrides}
    />,
  );
  return { onConfirm, onOpenChange };
};

describe("ReprocessDialog", () => {
  it("帶入 KB 預設值（ocr_mode / chunk_strategy / model 欄位）", () => {
    setup();
    expect(screen.getByLabelText("OCR 模式")).toHaveTextContent("商品目錄 DM");
    expect(screen.getByLabelText("分塊策略")).toHaveTextContent(
      "separator",
    );
    expect(screen.getByLabelText("OCR 模型")).toHaveValue(
      "anthropic:claude-sonnet-4-6",
    );
    expect(
      screen.getByLabelText("上下文模型 (Contextual Retrieval)"),
    ).toHaveValue("anthropic:claude-haiku-4-5");
  });

  it("沒帶 kbDefaults 時欄位走 fallback 預設", () => {
    setup({ kbDefaults: null });
    expect(screen.getByLabelText("OCR 模式")).toHaveTextContent("通用文字提取");
    expect(screen.getByLabelText("OCR 模型")).toHaveValue("");
    expect(
      screen.getByLabelText("上下文模型 (Contextual Retrieval)"),
    ).toHaveValue("");
  });

  it("送出 reprocess 應帶入當前欄位值（含 KB 預設帶入的）", async () => {
    const user = userEvent.setup();
    const { onConfirm } = setup();

    await user.click(screen.getByRole("button", { name: "重新處理" }));

    expect(onConfirm).toHaveBeenCalledWith({
      chunk_size: undefined,
      chunk_overlap: undefined,
      // KB.chunk_strategy = "separator" → "separator" 非 "auto" → 原樣送
      chunk_strategy: "separator",
      ocr_mode: "catalog",
      ocr_model: "anthropic:claude-sonnet-4-6",
      context_model: "anthropic:claude-haiku-4-5",
    });
  });

  it("「重設為 KB 預設」按鈕回復成 KB 設定", async () => {
    const user = userEvent.setup();
    const { onConfirm } = setup();

    // 先把 ocr_model 改空
    const ocrModelInput = screen.getByLabelText("OCR 模型");
    await user.clear(ocrModelInput);
    expect(ocrModelInput).toHaveValue("");

    // 點重設
    await user.click(screen.getByRole("button", { name: "重設為 KB 預設" }));
    expect(screen.getByLabelText("OCR 模型")).toHaveValue(
      "anthropic:claude-sonnet-4-6",
    );

    // 送出時應送回 KB 預設值
    await user.click(screen.getByRole("button", { name: "重新處理" }));
    const args = onConfirm.mock.calls[0][0];
    expect(args.ocr_model).toBe("anthropic:claude-sonnet-4-6");
  });

  it("chunk_strategy 'auto' 在送出時轉成空字串（後端視 auto = 預設）", async () => {
    const user = userEvent.setup();
    const kb: KnowledgeBase = { ...baseKb, chunk_strategy: "" };
    const { onConfirm } = setup({ kbDefaults: kb });

    await user.click(screen.getByRole("button", { name: "重新處理" }));

    expect(onConfirm).toHaveBeenCalledWith(
      expect.objectContaining({ chunk_strategy: "" }),
    );
  });

  it("空的 ocr_model / context_model 在送出時轉為 undefined（後端 fallback 到 KB）", async () => {
    const user = userEvent.setup();
    const kb: KnowledgeBase = {
      ...baseKb,
      ocr_model: "",
      context_model: "",
    };
    const { onConfirm } = setup({ kbDefaults: kb });

    await user.click(screen.getByRole("button", { name: "重新處理" }));

    expect(onConfirm).toHaveBeenCalledWith(
      expect.objectContaining({
        ocr_model: undefined,
        context_model: undefined,
      }),
    );
  });
});
