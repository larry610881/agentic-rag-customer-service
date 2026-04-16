/**
 * Pure TypeScript logic tests for contact button URL resolution.
 * DOM rendering 部分需要 jsdom，暫以純邏輯測試覆蓋 href 判斷。
 */
import { describe, it, expect } from "vitest";
import type { ContactCard } from "../types";

// 複製自 MessageList._resolveContactHref 的邏輯（純函式便於測試）
function resolveContactHref(contact: ContactCard): string {
  if (contact.type === "phone" && !contact.url.startsWith("tel:")) {
    return `tel:${contact.url}`;
  }
  return contact.url;
}

describe("resolveContactHref", () => {
  it("url 型別直接回傳原 URL", () => {
    const url = "https://carrefour.tototalk.com.tw/web-homepage";
    expect(
      resolveContactHref({ label: "客服", url, type: "url" }),
    ).toBe(url);
  });

  it("phone 型別自動加 tel: 前綴", () => {
    expect(
      resolveContactHref({ label: "撥打", url: "0800006006", type: "phone" }),
    ).toBe("tel:0800006006");
  });

  it("phone 型別已是 tel: 前綴不重複加", () => {
    expect(
      resolveContactHref({
        label: "撥打",
        url: "tel:0800-006-006",
        type: "phone",
      }),
    ).toBe("tel:0800-006-006");
  });
});
