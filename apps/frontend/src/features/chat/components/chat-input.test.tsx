import { describe, it, expect, beforeEach } from "vitest";
import { screen } from "@testing-library/react";
import { renderWithProviders, userEvent } from "@/test/test-utils";
import { ChatInput } from "@/features/chat/components/chat-input";
import { useChatStore } from "@/stores/use-chat-store";
import { useAuthStore } from "@/stores/use-auth-store";

describe("ChatInput", () => {
  beforeEach(() => {
    useChatStore.setState({
      messages: [],
      isStreaming: false,
      conversationId: null,
      botId: "bot-1",
      botName: "Test Bot",
    });
    useAuthStore.setState({ token: "test-token", tenantId: "tenant-1", tenants: [] });
  });

  it("should render input and send button", () => {
    renderWithProviders(<ChatInput />);
    expect(screen.getByRole("textbox", { name: "Message input" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Send" })).toBeInTheDocument();
  });

  it("should disable send button when input is empty", () => {
    renderWithProviders(<ChatInput />);
    expect(screen.getByRole("button", { name: "Send" })).toBeDisabled();
  });

  it("should enable send button when input has text", async () => {
    const user = userEvent.setup();
    renderWithProviders(<ChatInput />);
    await user.type(screen.getByRole("textbox", { name: "Message input" }), "Hello");
    expect(screen.getByRole("button", { name: "Send" })).toBeEnabled();
  });

  it("should disable send button when no bot is selected", async () => {
    useChatStore.setState({ botId: null, botName: null });
    const user = userEvent.setup();
    renderWithProviders(<ChatInput />);
    await user.type(screen.getByRole("textbox", { name: "Message input" }), "Hello");
    expect(screen.getByRole("button", { name: "Send" })).toBeDisabled();
  });

  it("should show sending state when streaming", () => {
    useChatStore.setState({ isStreaming: true });
    renderWithProviders(<ChatInput />);
    expect(screen.getByRole("button", { name: "Sending..." })).toBeDisabled();
  });
});
