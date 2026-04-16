import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { ContactCardButton } from "@/features/chat/components/contact-card-button";
import type { ContactCard } from "@/types/chat";

const card = (overrides: Partial<ContactCard> = {}): ContactCard => ({
  label: "聯絡真人客服",
  url: "https://carrefour.tototalk.com.tw/web-homepage",
  type: "url",
  ...overrides,
});

describe("ContactCardButton", () => {
  it("contact 為 undefined 時不渲染", () => {
    const { container } = render(<ContactCardButton contact={undefined} />);
    expect(container.firstChild).toBeNull();
  });

  it("有 contact 時渲染 anchor，href 為 contact.url", () => {
    render(<ContactCardButton contact={card()} />);
    const link = screen.getByRole("link", { name: /聯絡真人客服/ });
    expect(link).toHaveAttribute(
      "href",
      "https://carrefour.tototalk.com.tw/web-homepage",
    );
  });

  it("URL 型：target=_blank 新分頁開啟", () => {
    render(<ContactCardButton contact={card({ type: "url" })} />);
    const link = screen.getByRole("link");
    expect(link).toHaveAttribute("target", "_blank");
    expect(link).toHaveAttribute("rel", "noopener noreferrer");
  });

  it("phone 型：href 自動補 tel: 協議", () => {
    render(
      <ContactCardButton
        contact={card({ type: "phone", url: "0800-006-006" })}
      />,
    );
    const link = screen.getByRole("link");
    expect(link).toHaveAttribute("href", "tel:0800-006-006");
  });

  it("phone 型：target 不為 _blank（避免手機開新分頁奇怪）", () => {
    render(
      <ContactCardButton
        contact={card({ type: "phone", url: "0800-006-006" })}
      />,
    );
    const link = screen.getByRole("link");
    expect(link).not.toHaveAttribute("target", "_blank");
  });

  it("已經是 tel: 前綴的 url 不重覆加", () => {
    render(
      <ContactCardButton
        contact={card({ type: "phone", url: "tel:0800006006" })}
      />,
    );
    expect(screen.getByRole("link")).toHaveAttribute("href", "tel:0800006006");
  });

  it("label 為空時 fallback 為「聯絡客服」", () => {
    render(<ContactCardButton contact={card({ label: "" })} />);
    expect(
      screen.getByRole("link", { name: /聯絡客服/ }),
    ).toBeInTheDocument();
  });
});
