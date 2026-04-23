import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi, beforeEach } from "vitest";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { QualityTab } from "./quality-tab";

vi.mock("@/hooks/queries/use-kb-chunks", () => ({
  useKbQualitySummary: vi.fn(),
  useKbChunks: vi.fn(),
}));

import {
  useKbQualitySummary,
  useKbChunks,
} from "@/hooks/queries/use-kb-chunks";

const mockedSummary = vi.mocked(useKbQualitySummary);
const mockedChunks = vi.mocked(useKbChunks);

function renderWithClient(ui: React.ReactElement) {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={qc}>{ui}</QueryClientProvider>,
  );
}

describe("QualityTab", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("loading 狀態顯示載入文字", () => {
    mockedSummary.mockReturnValue({
      data: undefined,
      isLoading: true,
      error: null,
    } as unknown as ReturnType<typeof useKbQualitySummary>);
    mockedChunks.mockReturnValue({
      data: undefined,
      isLoading: true,
    } as unknown as ReturnType<typeof useKbChunks>);

    renderWithClient(<QualityTab kbId="kb-1" />);
    expect(screen.getByText("載入中...")).toBeInTheDocument();
  });

  it("error 狀態顯示錯誤訊息", () => {
    mockedSummary.mockReturnValue({
      data: undefined,
      isLoading: false,
      error: new Error("網路失敗"),
    } as unknown as ReturnType<typeof useKbQualitySummary>);
    mockedChunks.mockReturnValue({
      data: undefined,
      isLoading: false,
    } as unknown as ReturnType<typeof useKbChunks>);

    renderWithClient(<QualityTab kbId="kb-1" />);
    expect(screen.getByText(/載入失敗/)).toBeInTheDocument();
  });

  it("渲染 summary cards 與低品質 chunk 列表", () => {
    mockedSummary.mockReturnValue({
      data: {
        total_chunks: 500,
        low_quality_count: 60,
        avg_cohesion_score: 0.88,
      },
      isLoading: false,
      error: null,
    } as unknown as ReturnType<typeof useKbQualitySummary>);
    mockedChunks.mockReturnValue({
      data: {
        items: [
          {
            id: "chunk-1",
            document_id: "doc-1",
            tenant_id: "T001",
            content: "這個 chunk 太短了",
            context_text: "",
            chunk_index: 0,
            category_id: null,
            quality_flag: "too_short",
          },
          {
            id: "chunk-2",
            document_id: "doc-1",
            tenant_id: "T001",
            content: "正常 chunk",
            context_text: "",
            chunk_index: 1,
            category_id: null,
            quality_flag: null,
          },
        ],
        total: 500,
        page: 1,
        page_size: 200,
      },
      isLoading: false,
    } as unknown as ReturnType<typeof useKbChunks>);

    renderWithClient(<QualityTab kbId="kb-1" />);

    expect(screen.getByText("500")).toBeInTheDocument(); // total
    expect(screen.getByText("60")).toBeInTheDocument(); // low count
    expect(screen.getByText("0.8800")).toBeInTheDocument(); // avg_cohesion
    expect(screen.getByText("12.0%")).toBeInTheDocument(); // low ratio

    expect(screen.getByText("chunk-1")).toBeInTheDocument();
    expect(screen.getByText("這個 chunk 太短了")).toBeInTheDocument();
    expect(screen.queryByText("正常 chunk")).not.toBeInTheDocument();
  });

  it("點擊編輯按鈕呼叫 onEditChunk", async () => {
    const onEditChunk = vi.fn();
    mockedSummary.mockReturnValue({
      data: {
        total_chunks: 1,
        low_quality_count: 1,
        avg_cohesion_score: 0.0,
      },
      isLoading: false,
      error: null,
    } as unknown as ReturnType<typeof useKbQualitySummary>);
    mockedChunks.mockReturnValue({
      data: {
        items: [
          {
            id: "chunk-1",
            document_id: "doc-1",
            tenant_id: "T001",
            content: "x",
            context_text: "",
            chunk_index: 0,
            category_id: null,
            quality_flag: "too_short",
          },
        ],
        total: 1,
        page: 1,
        page_size: 200,
      },
      isLoading: false,
    } as unknown as ReturnType<typeof useKbChunks>);

    renderWithClient(<QualityTab kbId="kb-1" onEditChunk={onEditChunk} />);

    await userEvent.click(screen.getByRole("button", { name: "編輯" }));
    expect(onEditChunk).toHaveBeenCalledTimes(1);
    expect(onEditChunk).toHaveBeenCalledWith(
      expect.objectContaining({ id: "chunk-1" }),
    );
  });

  it("空狀態顯示 '取樣範圍無低品質 chunk'", () => {
    mockedSummary.mockReturnValue({
      data: { total_chunks: 10, low_quality_count: 0, avg_cohesion_score: 1 },
      isLoading: false,
      error: null,
    } as unknown as ReturnType<typeof useKbQualitySummary>);
    mockedChunks.mockReturnValue({
      data: { items: [], total: 0, page: 1, page_size: 200 },
      isLoading: false,
    } as unknown as ReturnType<typeof useKbChunks>);

    renderWithClient(<QualityTab kbId="kb-1" />);
    expect(
      screen.getByText("取樣範圍無低品質 chunk"),
    ).toBeInTheDocument();
  });
});
