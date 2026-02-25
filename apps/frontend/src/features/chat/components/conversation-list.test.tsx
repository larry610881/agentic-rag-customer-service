import { describe, it, expect, beforeEach } from "vitest";
import { screen, waitFor } from "@testing-library/react";
import { renderWithProviders, userEvent } from "@/test/test-utils";
import { ConversationList } from "@/features/chat/components/conversation-list";
import { useChatStore } from "@/stores/use-chat-store";
import { useAuthStore } from "@/stores/use-auth-store";

describe("ConversationList", () => {
  beforeEach(() => {
    useChatStore.setState({
      messages: [],
      isStreaming: false,
      conversationId: null,
      knowledgeBaseId: "kb-1",
      botId: "bot-1",
      botName: "Test Bot",
    });
    useAuthStore.setState({
      token: "test-token",
      tenantId: "tenant-1",
      tenants: [],
    });
  });

  it("should render the conversation list header and new button", () => {
    renderWithProviders(<ConversationList />);
    expect(screen.getByText("對話紀錄")).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "新對話" }),
    ).toBeInTheDocument();
  });

  it("should render conversation items from API", async () => {
    renderWithProviders(<ConversationList />);
    await waitFor(() => {
      expect(screen.getByText("conv-abc...")).toBeInTheDocument();
    });
    expect(screen.getByText("conv-def...")).toBeInTheDocument();
  });

  it("should highlight active conversation", async () => {
    useChatStore.setState({ conversationId: "conv-abc12345-1111" });
    renderWithProviders(<ConversationList />);
    await waitFor(() => {
      expect(screen.getByText("conv-abc...")).toBeInTheDocument();
    });
    const activeButton = screen.getByText("conv-abc...").closest("button");
    expect(activeButton).toHaveAttribute("aria-current", "true");
  });

  it("should clear messages when clicking New button", async () => {
    const user = userEvent.setup();
    useChatStore.setState({
      conversationId: "conv-abc12345-1111",
      messages: [
        {
          id: "msg-1",
          role: "user",
          content: "hello",
          timestamp: "2024-01-01T00:00:00Z",
        },
      ],
    });

    renderWithProviders(<ConversationList />);
    await user.click(
      screen.getByRole("button", { name: "新對話" }),
    );

    expect(useChatStore.getState().conversationId).toBeNull();
    expect(useChatStore.getState().messages).toHaveLength(0);
  });

  it("should filter conversations by bot_id", async () => {
    useChatStore.setState({
      messages: [],
      isStreaming: false,
      conversationId: null,
      knowledgeBaseId: "kb-1",
      botId: "bot-2",
      botName: "Bot 2",
    });
    renderWithProviders(<ConversationList />);
    await waitFor(() => {
      expect(screen.getByText("conv-ghi...")).toBeInTheDocument();
    });
    expect(screen.queryByText("conv-abc...")).not.toBeInTheDocument();
    expect(screen.queryByText("conv-def...")).not.toBeInTheDocument();
  });

  it("should show empty state when no conversations", async () => {
    useAuthStore.setState({ token: null, tenantId: null });
    renderWithProviders(<ConversationList />);
    expect(screen.getByText("尚無對話紀錄")).toBeInTheDocument();
  });

  it("should display bot name and switch button", () => {
    renderWithProviders(<ConversationList />);
    expect(screen.getByText("Test Bot")).toBeInTheDocument();
    expect(screen.getByText("切換")).toBeInTheDocument();
  });

  it("should clear bot when clicking switch button", async () => {
    const user = userEvent.setup();
    renderWithProviders(<ConversationList />);
    await user.click(screen.getByText("切換"));
    expect(useChatStore.getState().botId).toBeNull();
    expect(useChatStore.getState().botName).toBeNull();
  });
});
