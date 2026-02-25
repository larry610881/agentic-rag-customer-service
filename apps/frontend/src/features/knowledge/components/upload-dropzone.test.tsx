import { describe, it, expect, beforeEach } from "vitest";
import { screen } from "@testing-library/react";
import { renderWithProviders } from "@/test/test-utils";
import { UploadDropzone } from "@/features/knowledge/components/upload-dropzone";
import { useAuthStore } from "@/stores/use-auth-store";

describe("UploadDropzone", () => {
  beforeEach(() => {
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
});
