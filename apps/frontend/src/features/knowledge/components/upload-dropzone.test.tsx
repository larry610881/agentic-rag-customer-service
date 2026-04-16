import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { act, fireEvent, screen, waitFor } from "@testing-library/react";
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

function makeFile(name: string, type = "text/plain"): File {
  return new File(["content"], name, { type });
}

describe("UploadDropzone", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    useAuthStore.setState({
      token: "test-token",
      tenantId: "tenant-1",
      tenants: [],
    });
  });

  afterEach(() => {
    vi.useRealTimers();
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

  it("should show per-file error card when upload fails", async () => {
    const user = userEvent.setup();

    mockMutateAsync.mockRejectedValueOnce(new Error("Server error"));

    renderWithProviders(<UploadDropzone knowledgeBaseId="kb-1" />);

    const input = document.querySelector('input[type="file"]') as HTMLInputElement;
    const file = makeFile(
      "bad-file.docx",
      "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    );

    await user.upload(input, file);

    await waitFor(() => {
      expect(
        screen.getByRole("progressbar", { name: "上傳失敗：bad-file.docx" }),
      ).toBeInTheDocument();
    });
    // 錯誤訊息顯示在卡片中
    expect(screen.getByText("Server error")).toBeInTheDocument();
  });

  it("should show multiple per-file error cards for multi-file upload", async () => {
    const user = userEvent.setup();

    // 需要用 mockImplementation 逐一處理：第 1 個 resolve 永久 pending，其他 reject
    // 但為了測試「成功檔案不顯示錯誤」，讓第 1 個最終 resolve、另兩個 reject
    mockMutateAsync
      .mockResolvedValueOnce({ task_id: "t1" })
      .mockRejectedValueOnce(new Error("fail1 message"))
      .mockRejectedValueOnce(new Error("fail2 message"));

    renderWithProviders(<UploadDropzone knowledgeBaseId="kb-1" />);

    const input = document.querySelector('input[type="file"]') as HTMLInputElement;
    const files = [
      makeFile("good.txt"),
      makeFile(
        "fail1.docx",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
      ),
      makeFile("fail2.pdf", "application/pdf"),
    ];

    await user.upload(input, files);

    await waitFor(() => {
      expect(
        screen.getByRole("progressbar", { name: "上傳失敗：fail1.docx" }),
      ).toBeInTheDocument();
      expect(
        screen.getByRole("progressbar", { name: "上傳失敗：fail2.pdf" }),
      ).toBeInTheDocument();
    });
    expect(screen.getByText("fail1 message")).toBeInTheDocument();
    expect(screen.getByText("fail2 message")).toBeInTheDocument();
  });

  // --- 進度條 / 鎖定 相關 regression ---

  it("should show progressbar at 0% when upload starts", async () => {
    const user = userEvent.setup();
    mockMutateAsync.mockImplementation(() => new Promise(() => {})); // 永不 resolve

    renderWithProviders(<UploadDropzone knowledgeBaseId="kb-1" />);
    const input = document.querySelector('input[type="file"]') as HTMLInputElement;

    await user.upload(input, makeFile("big.pdf", "application/pdf"));

    await waitFor(() => {
      const bar = screen.getByRole("progressbar", { name: "上傳中：big.pdf" });
      expect(bar).toHaveAttribute("aria-valuenow", "0");
    });
  });

  it("should update progressbar when onProgress callback fires", async () => {
    const user = userEvent.setup();
    let capturedOnProgress: ((pct: number) => void) | undefined;
    mockMutateAsync.mockImplementation(
      ({ onProgress }: { onProgress?: (pct: number) => void }) => {
        capturedOnProgress = onProgress;
        return new Promise(() => {}); // 永不 resolve
      },
    );

    renderWithProviders(<UploadDropzone knowledgeBaseId="kb-1" />);
    const input = document.querySelector('input[type="file"]') as HTMLInputElement;

    await user.upload(input, makeFile("big.pdf", "application/pdf"));

    await waitFor(() => {
      expect(screen.getByRole("progressbar", { name: "上傳中：big.pdf" })).toBeInTheDocument();
    });

    act(() => {
      capturedOnProgress?.(42);
    });

    await waitFor(() => {
      const bar = screen.getByRole("progressbar", { name: "上傳中：big.pdf" });
      expect(bar).toHaveAttribute("aria-valuenow", "42");
    });
  });

  it("should disable choose-file button during upload", async () => {
    const user = userEvent.setup();
    mockMutateAsync.mockImplementation(() => new Promise(() => {}));

    renderWithProviders(<UploadDropzone knowledgeBaseId="kb-1" />);
    const input = document.querySelector('input[type="file"]') as HTMLInputElement;

    await user.upload(input, makeFile("foo.pdf", "application/pdf"));

    await waitFor(() => {
      expect(screen.getByText("選擇檔案").closest("button")).toBeDisabled();
    });
  });

  it("should disable file input during upload", async () => {
    const user = userEvent.setup();
    mockMutateAsync.mockImplementation(() => new Promise(() => {}));

    renderWithProviders(<UploadDropzone knowledgeBaseId="kb-1" />);
    const input = document.querySelector('input[type="file"]') as HTMLInputElement;

    await user.upload(input, makeFile("foo.pdf", "application/pdf"));

    await waitFor(() => {
      expect(input).toBeDisabled();
    });
  });

  it("should mark dropzone as aria-busy during upload", async () => {
    const user = userEvent.setup();
    mockMutateAsync.mockImplementation(() => new Promise(() => {}));

    renderWithProviders(<UploadDropzone knowledgeBaseId="kb-1" />);
    const input = document.querySelector('input[type="file"]') as HTMLInputElement;

    await user.upload(input, makeFile("foo.pdf", "application/pdf"));

    await waitFor(() => {
      const region = screen.getByRole("region", { name: "上傳區域" });
      expect(region).toHaveAttribute("aria-busy", "true");
      expect(region).toHaveAttribute("aria-disabled", "true");
    });
  });

  it("should ignore drop events while locked", async () => {
    const user = userEvent.setup();
    mockMutateAsync.mockImplementation(() => new Promise(() => {}));

    renderWithProviders(<UploadDropzone knowledgeBaseId="kb-1" />);
    const input = document.querySelector('input[type="file"]') as HTMLInputElement;

    await user.upload(input, makeFile("first.pdf", "application/pdf"));

    await waitFor(() => {
      expect(mockMutateAsync).toHaveBeenCalledTimes(1);
    });

    // drag new file while locked
    const region = screen.getByRole("region", { name: "上傳區域" });
    const newFile = makeFile("second.pdf", "application/pdf");
    fireEvent.drop(region, {
      dataTransfer: { files: [newFile] },
    });

    // mutateAsync 不應再被呼叫
    expect(mockMutateAsync).toHaveBeenCalledTimes(1);
  });

  it("should render independent progressbars for 3 concurrent uploads", async () => {
    const user = userEvent.setup();
    mockMutateAsync.mockImplementation(() => new Promise(() => {}));

    renderWithProviders(<UploadDropzone knowledgeBaseId="kb-1" />);
    const input = document.querySelector('input[type="file"]') as HTMLInputElement;

    const files = [
      makeFile("a.pdf", "application/pdf"),
      makeFile("b.pdf", "application/pdf"),
      makeFile("c.pdf", "application/pdf"),
    ];
    await user.upload(input, files);

    await waitFor(() => {
      expect(screen.getAllByRole("progressbar")).toHaveLength(3);
    });
  });

  it("should dismiss success card after 2 seconds", async () => {
    const user = userEvent.setup();
    mockMutateAsync.mockResolvedValueOnce({ task_id: "t1" });

    renderWithProviders(<UploadDropzone knowledgeBaseId="kb-1" />);
    const input = document.querySelector('input[type="file"]') as HTMLInputElement;

    await user.upload(input, makeFile("ok.pdf", "application/pdf"));

    await waitFor(() => {
      expect(
        screen.getByRole("progressbar", { name: "上傳成功：ok.pdf" }),
      ).toBeInTheDocument();
    });

    // 等 real-timer setTimeout(2000) 觸發後卡片消失
    await waitFor(
      () => {
        expect(
          screen.queryByRole("progressbar", { name: "上傳成功：ok.pdf" }),
        ).not.toBeInTheDocument();
      },
      { timeout: 3000 },
    );
  });
});
