import { describe, it, expect, beforeEach, vi } from "vitest";
import { screen } from "@testing-library/react";
import { renderWithProviders, userEvent } from "@/test/test-utils";
import { BotSelector } from "@/features/chat/components/bot-selector";
import { useChatStore } from "@/stores/use-chat-store";

const useBotsMock = vi.fn();
vi.mock("@/hooks/queries/use-bots", () => ({
  useBots: () => useBotsMock(),
}));

function bots(n: number) {
  return Array.from({ length: n }, (_, i) => ({
    id: `bot-${i + 1}`,
    name: `機器人 ${i + 1}`,
    description: "",
    is_active: true,
    knowledge_base_ids: [],
  }));
}

function listContainer(): HTMLElement {
  // 標題區塊的父層＝清單分支的最外層容器
  const heading = screen.getByRole("heading", { name: "選擇一個機器人開始對話" });
  return heading.parentElement!.parentElement!;
}

describe("BotSelector 清單分支版面（Bug #470083）", () => {
  beforeEach(() => {
    useChatStore.setState({ botId: null, botName: null });
  });

  it("外層不可同時鎖高度（h-full）又 justify-center：超高時往上溢出的部分捲不到", () => {
    useBotsMock.mockReturnValue({
      data: { items: bots(20) },
      isLoading: false,
      isError: false,
    });
    renderWithProviders(<BotSelector />);
    const cls = listContainer().className.split(/\s+/);
    // 內容少時仍能撐滿並置中；內容多時容器跟著長高，由 main 捲動
    expect(cls).toContain("min-h-full");
    expect(cls).not.toContain("h-full");
    expect(cls).toContain("justify-center");
  });

  it("20 隻機器人時第一張與最後一張都渲染且可點選", async () => {
    useBotsMock.mockReturnValue({
      data: { items: bots(20) },
      isLoading: false,
      isError: false,
    });
    renderWithProviders(<BotSelector />);
    const cards = screen.getAllByRole("button");
    expect(cards).toHaveLength(20);
    await userEvent.click(screen.getByRole("button", { name: /機器人 20(?!\d)/ }));
    expect(useChatStore.getState().botId).toBe("bot-20");
    useChatStore.setState({ botId: null, botName: null });
    await userEvent.click(screen.getByRole("button", { name: /機器人 1(?!\d)/ }));
    expect(useChatStore.getState().botId).toBe("bot-1");
  });
});
