import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ToolRagConfigSection } from "./tool-rag-config-section";
import type { ToolRagConfig } from "@/types/bot";

const inherited = {
  rag_top_k: 5,
  rag_score_threshold: 0.3,
  rerank_enabled: false,
  rerank_model: "claude-haiku-4-5-20251001",
  rerank_top_n: 20,
};

const modelOptions = [
  { value: "claude-haiku-4-5-20251001", label: "Claude Haiku 4.5" },
  { value: "claude-sonnet-4-20250514", label: "Claude Sonnet 4" },
];

describe("ToolRagConfigSection", () => {
  const onChange = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders tool label as summary (collapsed by default)", () => {
    render(
      <ToolRagConfigSection
        toolName="rag_query"
        toolLabel="知識庫查詢"
        value={undefined}
        inherited={inherited}
        onChange={onChange}
        rerankModelOptions={modelOptions}
      />,
    );
    expect(screen.getByText("知識庫查詢")).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /進階設定/ }),
    ).toBeInTheDocument();
    // collapsed => advanced fields not visible
    expect(
      screen.queryByLabelText(/Top K/),
    ).not.toBeInTheDocument();
  });

  it("expands to show all fields with inherited placeholders when no override", async () => {
    const user = userEvent.setup();
    render(
      <ToolRagConfigSection
        toolName="rag_query"
        toolLabel="知識庫查詢"
        value={undefined}
        inherited={inherited}
        onChange={onChange}
        rerankModelOptions={modelOptions}
      />,
    );
    await user.click(screen.getByRole("button", { name: /進階設定/ }));
    const topK = screen.getByLabelText(/Top K/) as HTMLInputElement;
    expect(topK.value).toBe("");
    expect(topK.placeholder).toContain("5");

    const thresh = screen.getByLabelText(/分數閾值/) as HTMLInputElement;
    expect(thresh.value).toBe("");
    expect(thresh.placeholder).toContain("0.3");

    const topN = screen.getByLabelText(/Rerank Top N|召回數量/) as HTMLInputElement;
    expect(topN.value).toBe("");
    expect(topN.placeholder).toContain("20");
  });

  it("shows inheritedLabel text in placeholder", async () => {
    const user = userEvent.setup();
    render(
      <ToolRagConfigSection
        toolName="rag_query"
        toolLabel="知識庫查詢"
        value={undefined}
        inherited={inherited}
        inheritedLabel="繼承自 Bot 的 rag_query"
        onChange={onChange}
        rerankModelOptions={modelOptions}
      />,
    );
    await user.click(screen.getByRole("button", { name: /進階設定/ }));
    const topK = screen.getByLabelText(/Top K/) as HTMLInputElement;
    expect(topK.placeholder).toContain("繼承自 Bot 的 rag_query");
  });

  it("calls onChange with partial override when only top_k is set", async () => {
    const user = userEvent.setup();
    render(
      <ToolRagConfigSection
        toolName="rag_query"
        toolLabel="知識庫查詢"
        value={undefined}
        inherited={inherited}
        onChange={onChange}
        rerankModelOptions={modelOptions}
      />,
    );
    await user.click(screen.getByRole("button", { name: /進階設定/ }));
    const topK = screen.getByLabelText(/Top K/);
    await user.type(topK, "7");

    // last call should have rag_top_k=7 and no other keys
    const lastCall = onChange.mock.calls[onChange.mock.calls.length - 1][0];
    expect(lastCall).toEqual({ rag_top_k: 7 });
  });

  it("renders existing override value in input", async () => {
    const user = userEvent.setup();
    const value: ToolRagConfig = { rag_top_k: 10, rerank_enabled: true };
    render(
      <ToolRagConfigSection
        toolName="query_dm_with_image"
        toolLabel="DM 圖卡查詢"
        value={value}
        inherited={inherited}
        onChange={onChange}
        rerankModelOptions={modelOptions}
      />,
    );
    await user.click(screen.getByRole("button", { name: /進階設定/ }));
    const topK = screen.getByLabelText(/Top K/) as HTMLInputElement;
    expect(topK.value).toBe("10");
  });

  it("reset-to-inherit button clears the override (calls onChange(undefined))", async () => {
    const user = userEvent.setup();
    const value: ToolRagConfig = { rag_top_k: 10 };
    render(
      <ToolRagConfigSection
        toolName="rag_query"
        toolLabel="知識庫查詢"
        value={value}
        inherited={inherited}
        onChange={onChange}
        rerankModelOptions={modelOptions}
      />,
    );
    await user.click(screen.getByRole("button", { name: /進階設定/ }));
    await user.click(screen.getByRole("button", { name: /重設為繼承/ }));
    expect(onChange).toHaveBeenLastCalledWith(undefined);
  });

  it("rerank_enabled tri-state: default (inherit) / on / off", async () => {
    const user = userEvent.setup();
    render(
      <ToolRagConfigSection
        toolName="rag_query"
        toolLabel="知識庫查詢"
        value={undefined}
        inherited={inherited}
        onChange={onChange}
        rerankModelOptions={modelOptions}
        defaultExpanded
      />,
    );
    // Inherit option should be visible as the current value label
    expect(screen.getByText(/跟隨繼承/)).toBeInTheDocument();
    // Tri-state select is labelled by "Reranking"
    expect(screen.getByLabelText(/Reranking/)).toBeInTheDocument();
    void user; // silence unused
  });

  it("setting a field back to empty removes that key from override", async () => {
    const user = userEvent.setup();
    const value: ToolRagConfig = { rag_top_k: 7 };
    render(
      <ToolRagConfigSection
        toolName="rag_query"
        toolLabel="知識庫查詢"
        value={value}
        inherited={inherited}
        onChange={onChange}
        rerankModelOptions={modelOptions}
      />,
    );
    await user.click(screen.getByRole("button", { name: /進階設定/ }));
    const topK = screen.getByLabelText(/Top K/) as HTMLInputElement;
    await user.clear(topK);
    // Clearing the only set key => final value should become undefined
    expect(onChange).toHaveBeenLastCalledWith(undefined);
  });
});
