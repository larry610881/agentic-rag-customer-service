import { describe, it, expect, beforeEach } from "vitest";
import { screen } from "@testing-library/react";
import { renderWithProviders } from "@/test/test-utils";
import { MessageList } from "@/features/chat/components/message-list";
import { useChatStore } from "@/stores/use-chat-store";
import { mockMessages } from "@/test/fixtures/chat";

describe("MessageList", () => {
  beforeEach(() => {
    useChatStore.setState({
      messages: [],
      isStreaming: false,
      conversationId: null,
      knowledgeBaseId: null,
    });
  });

  it("should show empty state when no messages", () => {
    renderWithProviders(<MessageList />);
    expect(
      screen.getByText("傳送訊息開始對話。"),
    ).toBeInTheDocument();
  });

  it("should render user and assistant messages", () => {
    useChatStore.setState({ messages: mockMessages });
    renderWithProviders(<MessageList />);
    expect(screen.getByText("What is the return policy?")).toBeInTheDocument();
    expect(
      screen.getByText(
        "Based on the information I found, returns are accepted within 30 days.",
      ),
    ).toBeInTheDocument();
  });

  it("should render citations for assistant messages with sources", () => {
    useChatStore.setState({ messages: mockMessages });
    renderWithProviders(<MessageList />);
    expect(screen.getByText("參考來源")).toBeInTheDocument();
    expect(screen.getByText("product-guide.pdf")).toBeInTheDocument();
  });

  it("should render agent thought panel for messages with tool calls", () => {
    useChatStore.setState({ messages: mockMessages });
    renderWithProviders(<MessageList />);
    expect(screen.getByText("Agent 操作（1）")).toBeInTheDocument();
  });
});
