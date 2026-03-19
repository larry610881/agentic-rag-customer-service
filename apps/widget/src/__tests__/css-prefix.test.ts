import { describe, it, expect } from "vitest";
import { cls, CSS_PREFIX } from "../constants";

describe("CSS Prefix", () => {
  it("should default to 'aw' prefix", () => {
    expect(CSS_PREFIX).toBe("aw");
  });

  it("cls() should produce 'aw-' prefixed class names", () => {
    expect(cls("fab")).toBe("aw-fab");
    expect(cls("chat-panel")).toBe("aw-chat-panel");
  });

  it("should produce correct class names for common widget elements", () => {
    const elements = ["fab", "panel", "messages", "header", "input", "bubble"];
    for (const el of elements) {
      expect(cls(el)).toBe(`aw-${el}`);
    }
  });

  it("should handle BEM modifiers correctly", () => {
    expect(cls("fab--open")).toBe("aw-fab--open");
    expect(cls("bubble--user")).toBe("aw-bubble--user");
    expect(cls("feedback__btn--active")).toBe("aw-feedback__btn--active");
  });

  it("should handle BEM elements correctly", () => {
    expect(cls("header__name")).toBe("aw-header__name");
    expect(cls("sources__toggle")).toBe("aw-sources__toggle");
    expect(cls("fab__icon-chat")).toBe("aw-fab__icon-chat");
  });
});
