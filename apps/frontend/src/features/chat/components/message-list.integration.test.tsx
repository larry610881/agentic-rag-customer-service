import { describe, it, expect, beforeEach } from "vitest";
import { screen, act } from "@testing-library/react";
import { renderWithProviders } from "@/test/test-utils";
import { MessageList } from "@/features/chat/components/message-list";
import { useChatStore } from "@/stores/use-chat-store";
import { mockMessages } from "@/test/fixtures/chat";

describe("MessageList integration", () => {
  beforeEach(() => {
    useChatStore.setState({
      messages: [],
      isStreaming: false,
      conversationId: null,
      knowledgeBaseId: null,
    });
  });

  it("should display full conversation with citations and tool calls", () => {
    useChatStore.setState({ messages: mockMessages });
    renderWithProviders(<MessageList />);

    // 使用者訊息
    expect(screen.getByText("What is the return policy?")).toBeInTheDocument();

    // 助理訊息
    expect(
      screen.getByText(
        "Based on the information I found, returns are accepted within 30 days.",
      ),
    ).toBeInTheDocument();

    // 參考來源
    expect(screen.getByText("參考來源")).toBeInTheDocument();
    expect(screen.getByText("product-guide.pdf")).toBeInTheDocument();
    expect(screen.getByText("faq.pdf")).toBeInTheDocument();

    // 工具呼叫
    expect(screen.getByText("Agent 操作（2）")).toBeInTheDocument();
  });

  it("should show empty state and then messages when conversation starts", () => {
    renderWithProviders(<MessageList />);
    expect(
      screen.getByText("傳送訊息開始對話。"),
    ).toBeInTheDocument();

    // 模擬新增訊息 — 包裹在 act 中以處理 React 狀態更新
    act(() => {
      useChatStore.getState().addUserMessage("Hello");
    });

    // 透過 Zustand subscription 觸發重新渲染
    expect(screen.queryByText("傳送訊息開始對話。")).not.toBeInTheDocument();
    expect(screen.getByText("Hello")).toBeInTheDocument();
  });
});
