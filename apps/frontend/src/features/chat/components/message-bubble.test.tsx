import { screen } from "@testing-library/react";
import { beforeEach, describe, expect, it } from "vitest";

import { MessageBubble } from "@/features/chat/components/message-bubble";
import { renderWithProviders } from "@/test/test-utils";
import { useChatStore } from "@/stores/use-chat-store";
import type { ChatMessage } from "@/types/chat";

const BASE: ChatMessage = {
  id: "m-1",
  role: "assistant",
  content: "本月額度已用完，請聯繫管理員",
  timestamp: "2026-09-07T00:00:00Z",
};

describe("MessageBubble — Issue #74 額度用盡通知", () => {
  beforeEach(() => {
    useChatStore.setState({
      messages: [],
      isStreaming: false,
      conversationId: "conv-1",
      toolHint: null,
    });
  });

  it("quotaExhausted 訊息以通知樣式呈現文案，且不顯示回饋按鈕", () => {
    renderWithProviders(<MessageBubble message={{ ...BASE, quotaExhausted: true }} />);

    expect(screen.getByRole("status")).toHaveTextContent("本月額度已用完，服務暫停");
    expect(screen.getByText("本月額度已用完，請聯繫管理員")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /讚|倒讚|thumbs/i })).not.toBeInTheDocument();
  });

  it("一般 assistant 訊息沒有通知橫幅", () => {
    renderWithProviders(<MessageBubble message={BASE} />);

    expect(screen.queryByRole("status")).not.toBeInTheDocument();
    expect(screen.getByText("本月額度已用完，請聯繫管理員")).toBeInTheDocument();
  });
});
