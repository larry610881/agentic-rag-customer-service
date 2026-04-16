import { describe, it, expect } from "vitest";
import { extractGalleryImages } from "../chat/message-list";
import type { Source } from "../types";

const imgSource = (overrides: Partial<Source> = {}): Source => ({
  document_name: "家樂福 DM",
  content_snippet: "衛生紙 $99",
  score: 0.95,
  document_id: "doc-1",
  page_number: 3,
  image_url: "https://example.com/dm/page-3.png",
  ...overrides,
});

describe("extractGalleryImages", () => {
  it("空 sources → 空陣列", () => {
    expect(extractGalleryImages([])).toEqual([]);
  });

  it("完全沒有 image_url 的 sources → 空陣列", () => {
    const plain: Source = {
      document_name: "FAQ",
      content_snippet: "退貨",
      score: 0.8,
    };
    expect(extractGalleryImages([plain])).toEqual([]);
  });

  it("有 image_url 的 source 保留", () => {
    const result = extractGalleryImages([imgSource()]);
    expect(result).toHaveLength(1);
    expect(result[0].src).toBe("https://example.com/dm/page-3.png");
    expect(result[0].documentName).toBe("家樂福 DM");
    expect(result[0].pageNumber).toBe(3);
  });

  it("混合 sources 只保留有 image_url 的", () => {
    const plain: Source = {
      document_name: "FAQ",
      content_snippet: "退貨",
      score: 0.8,
    };
    const result = extractGalleryImages([imgSource(), plain]);
    expect(result).toHaveLength(1);
    expect(result[0].src).toBe("https://example.com/dm/page-3.png");
  });

  it("相同 document_id + page_number 去重，保留分數高者", () => {
    const hi = imgSource({ score: 0.9, image_url: "https://ex.com/a.png" });
    const lo = imgSource({ score: 0.5, image_url: "https://ex.com/b.png" });
    const result = extractGalleryImages([lo, hi]);
    expect(result).toHaveLength(1);
    expect(result[0].src).toBe("https://ex.com/a.png");
    expect(result[0].score).toBe(0.9);
  });

  it("不同 page_number 視為不同圖（保留）", () => {
    const p1 = imgSource({ page_number: 1, image_url: "https://ex.com/1.png" });
    const p2 = imgSource({ page_number: 2, image_url: "https://ex.com/2.png" });
    const result = extractGalleryImages([p1, p2]);
    expect(result).toHaveLength(2);
  });

  it("不同 document_id 視為不同圖", () => {
    const a = imgSource({ document_id: "a", image_url: "https://ex.com/a.png" });
    const b = imgSource({ document_id: "b", image_url: "https://ex.com/b.png" });
    const result = extractGalleryImages([a, b]);
    expect(result).toHaveLength(2);
  });
});
