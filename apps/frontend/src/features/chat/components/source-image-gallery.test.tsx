import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { SourceImageGallery } from "@/features/chat/components/source-image-gallery";
import type { Source } from "@/types/chat";

const imgSource = (overrides: Partial<Source> = {}): Source => ({
  document_name: "家樂福 DM",
  content_snippet: "衛生紙 $99",
  score: 0.95,
  document_id: "doc-1",
  page_number: 3,
  image_url: "https://example.com/dm/page-3.png",
  ...overrides,
});

describe("SourceImageGallery", () => {
  it("無任何 sources 時不渲染", () => {
    const { container } = render(<SourceImageGallery sources={[]} />);
    expect(container.firstChild).toBeNull();
  });

  it("sources 都沒有 image_url 時不渲染", () => {
    const plain: Source = {
      document_name: "FAQ",
      content_snippet: "退貨政策",
      score: 0.8,
    };
    const { container } = render(<SourceImageGallery sources={[plain]} />);
    expect(container.firstChild).toBeNull();
  });

  it("有 image_url 的 source 渲染為圖片", () => {
    render(<SourceImageGallery sources={[imgSource()]} />);
    const img = screen.getByRole("img");
    expect(img).toHaveAttribute(
      "src",
      "https://example.com/dm/page-3.png",
    );
  });

  it("只渲染有 image_url 的 sources（過濾）", () => {
    const plain: Source = {
      document_name: "FAQ",
      content_snippet: "退貨",
      score: 0.8,
    };
    render(
      <SourceImageGallery
        sources={[imgSource({ document_name: "DM-A" }), plain]}
      />,
    );
    const imgs = screen.getAllByRole("img");
    expect(imgs).toHaveLength(1);
  });

  it("相同 document_id + page_number 去重，只保留分數高者", () => {
    const hi = imgSource({ score: 0.9, image_url: "https://ex.com/a.png" });
    const lo = imgSource({ score: 0.5, image_url: "https://ex.com/b.png" });
    render(<SourceImageGallery sources={[lo, hi]} />);
    const imgs = screen.getAllByRole("img");
    expect(imgs).toHaveLength(1);
    expect(imgs[0]).toHaveAttribute("src", "https://ex.com/a.png");
  });

  it("圖片 alt 文字包含 document_name 與頁碼", () => {
    render(<SourceImageGallery sources={[imgSource()]} />);
    const img = screen.getByRole("img");
    expect(img).toHaveAttribute(
      "alt",
      expect.stringContaining("家樂福 DM"),
    );
    expect(img).toHaveAttribute("alt", expect.stringContaining("3"));
  });

  it("點擊圖片開新分頁顯示原圖", () => {
    render(<SourceImageGallery sources={[imgSource()]} />);
    const link = screen.getByRole("link");
    expect(link).toHaveAttribute(
      "href",
      "https://example.com/dm/page-3.png",
    );
    expect(link).toHaveAttribute("target", "_blank");
    expect(link).toHaveAttribute("rel", "noopener noreferrer");
  });

  it("variant=full 使用多欄 grid（data 屬性可供樣式掛鉤）", () => {
    const { container } = render(
      <SourceImageGallery sources={[imgSource()]} variant="full" />,
    );
    const root = container.querySelector("[data-variant='full']");
    expect(root).not.toBeNull();
  });

  it("variant=compact 單欄（data 屬性）", () => {
    const { container } = render(
      <SourceImageGallery sources={[imgSource()]} variant="compact" />,
    );
    const root = container.querySelector("[data-variant='compact']");
    expect(root).not.toBeNull();
  });

  it("預設 variant=full", () => {
    const { container } = render(
      <SourceImageGallery sources={[imgSource()]} />,
    );
    expect(
      container.querySelector("[data-variant='full']"),
    ).not.toBeNull();
  });

  it("header 顯示張數統計", () => {
    render(
      <SourceImageGallery
        sources={[
          imgSource({ page_number: 1, image_url: "https://ex.com/1.png" }),
          imgSource({ page_number: 2, image_url: "https://ex.com/2.png" }),
          imgSource({ page_number: 3, image_url: "https://ex.com/3.png" }),
        ]}
      />,
    );
    expect(screen.getByText(/參考圖片（3）/)).toBeInTheDocument();
  });
});
