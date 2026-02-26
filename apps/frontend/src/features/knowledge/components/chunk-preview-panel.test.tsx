import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { ChunkPreviewPanel } from "./chunk-preview-panel";
import type { ChunkPreviewResponse } from "@/types/knowledge";

const mockChunkData: ChunkPreviewResponse = {
  chunks: [
    { id: "c1", content: "Normal chunk content that is long enough.", chunk_index: 0, issues: [] },
    { id: "c2", content: "Short", chunk_index: 1, issues: ["too_short"] },
    { id: "c3", content: "This chunk has a mid-sentence break issue and is long enough", chunk_index: 2, issues: ["mid_sentence_break"] },
  ],
  total: 10,
};

vi.mock("@/hooks/queries/use-document-chunks", () => ({
  useDocumentChunks: vi.fn(() => ({
    data: mockChunkData,
    isLoading: false,
  })),
}));

describe("ChunkPreviewPanel", () => {
  it("renders nothing when closed", () => {
    const { container } = render(
      <ChunkPreviewPanel kbId="kb-1" docId="doc-1" open={false} />,
    );
    expect(container.firstChild).toBeNull();
  });

  it("renders chunk list when open", () => {
    render(<ChunkPreviewPanel kbId="kb-1" docId="doc-1" open={true} />);
    expect(screen.getByTestId("chunk-preview-panel")).toBeInTheDocument();
    expect(screen.getByText("共 10 個分塊（顯示前 3 個）")).toBeInTheDocument();
  });

  it("highlights too_short chunks with issue badge", () => {
    render(<ChunkPreviewPanel kbId="kb-1" docId="doc-1" open={true} />);
    expect(screen.getByTestId("issue-too_short")).toHaveTextContent("過短");
  });

  it("highlights mid_sentence_break chunks with issue badge", () => {
    render(<ChunkPreviewPanel kbId="kb-1" docId="doc-1" open={true} />);
    expect(screen.getByTestId("issue-mid_sentence_break")).toHaveTextContent("斷句不完整");
  });

  it("shows chunk index for each chunk", () => {
    render(<ChunkPreviewPanel kbId="kb-1" docId="doc-1" open={true} />);
    expect(screen.getByTestId("chunk-0")).toBeInTheDocument();
    expect(screen.getByTestId("chunk-1")).toBeInTheDocument();
    expect(screen.getByTestId("chunk-2")).toBeInTheDocument();
  });
});
