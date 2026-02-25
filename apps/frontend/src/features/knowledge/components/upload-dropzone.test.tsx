import { describe, it, expect, beforeEach, vi } from "vitest";
import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { renderWithProviders } from "@/test/test-utils";
import { UploadDropzone } from "@/features/knowledge/components/upload-dropzone";
import { useAuthStore } from "@/stores/use-auth-store";

// Mock useUploadDocument
const mockMutateAsync = vi.fn();
vi.mock("@/hooks/queries/use-documents", () => ({
  useUploadDocument: () => ({
    mutateAsync: mockMutateAsync,
    isError: false,
  }),
}));

describe("UploadDropzone", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    useAuthStore.setState({
      token: "test-token",
      tenantId: "tenant-1",
      tenants: [],
    });
  });

  it("should render dropzone with instructions", () => {
    renderWithProviders(<UploadDropzone knowledgeBaseId="kb-1" />);
    expect(
      screen.getByText("拖曳檔案至此處，或點擊選擇檔案"),
    ).toBeInTheDocument();
  });

  it("should render choose file button", () => {
    renderWithProviders(<UploadDropzone knowledgeBaseId="kb-1" />);
    expect(screen.getByText("選擇檔案")).toBeInTheDocument();
  });

  it("should have upload region with proper label", () => {
    renderWithProviders(<UploadDropzone knowledgeBaseId="kb-1" />);
    expect(screen.getByRole("region", { name: "上傳區域" })).toBeInTheDocument();
  });

  it("should show per-file error when upload fails", async () => {
    const user = userEvent.setup();

    mockMutateAsync.mockRejectedValueOnce(new Error("Server error"));

    renderWithProviders(<UploadDropzone knowledgeBaseId="kb-1" />);

    const input = document.querySelector('input[type="file"]') as HTMLInputElement;
    const file = new File(["content"], "bad-file.docx", {
      type: "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    });

    await user.upload(input, file);

    await waitFor(() => {
      expect(screen.getByText("bad-file.docx: 上傳失敗")).toBeInTheDocument();
    });
  });

  it("should show multiple per-file errors for multi-file upload", async () => {
    const user = userEvent.setup();

    mockMutateAsync
      .mockResolvedValueOnce({ task_id: "t1" })
      .mockRejectedValueOnce(new Error("fail"))
      .mockRejectedValueOnce(new Error("fail"));

    renderWithProviders(<UploadDropzone knowledgeBaseId="kb-1" />);

    const input = document.querySelector('input[type="file"]') as HTMLInputElement;
    const files = [
      new File(["ok"], "good.txt", { type: "text/plain" }),
      new File(["bad1"], "fail1.docx", { type: "application/vnd.openxmlformats-officedocument.wordprocessingml.document" }),
      new File(["bad2"], "fail2.pdf", { type: "application/pdf" }),
    ];

    await user.upload(input, files);

    await waitFor(() => {
      expect(screen.getByText("fail1.docx: 上傳失敗")).toBeInTheDocument();
      expect(screen.getByText("fail2.pdf: 上傳失敗")).toBeInTheDocument();
    });

    // 成功的檔案不應出現在錯誤列表
    expect(screen.queryByText("good.txt: 上傳失敗")).not.toBeInTheDocument();
  });
});
