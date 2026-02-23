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

    // User message
    expect(screen.getByText("What is the return policy?")).toBeInTheDocument();

    // Assistant message
    expect(
      screen.getByText(
        "Based on the information I found, returns are accepted within 30 days.",
      ),
    ).toBeInTheDocument();

    // Citations
    expect(screen.getByText("Sources")).toBeInTheDocument();
    expect(screen.getByText("product-guide.pdf")).toBeInTheDocument();
    expect(screen.getByText("faq.pdf")).toBeInTheDocument();

    // Tool calls
    expect(screen.getByText("Agent Actions (2)")).toBeInTheDocument();
  });

  it("should show empty state and then messages when conversation starts", () => {
    renderWithProviders(<MessageList />);
    expect(
      screen.getByText("Start a conversation by sending a message."),
    ).toBeInTheDocument();

    // Simulate adding a message - wrapped in act for React state update
    act(() => {
      useChatStore.getState().addUserMessage("Hello");
    });

    // Re-render happens through Zustand subscription
    expect(screen.queryByText("Start a conversation by sending a message.")).not.toBeInTheDocument();
    expect(screen.getByText("Hello")).toBeInTheDocument();
  });
});
