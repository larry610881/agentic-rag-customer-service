import { act, renderHook } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { useStreaming } from "@/features/chat/hooks/use-streaming";
import { useAuthStore } from "@/stores/use-auth-store";
import { useChatStore } from "@/stores/use-chat-store";
import type { SSEEvent } from "@/lib/sse-client";

vi.mock("@/lib/sse-client", () => ({
  fetchSSE: vi.fn(),
}));

import { fetchSSE } from "@/lib/sse-client";

const fetchSSEMock = vi.mocked(fetchSSE);

/** 讓 mock 依序吐出事件 */
function emit(events: SSEEvent[]) {
  fetchSSEMock.mockImplementation(async (_url, _body, _token, onEvent) => {
    for (const e of events) onEvent(e);
  });
}

describe("useStreaming — Issue #74 quota_exhausted", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    useAuthStore.setState({ token: "tok", tenantId: "tenant-1" });
    useChatStore.setState({
      messages: [],
      isStreaming: false,
      conversationId: null,
      botId: "bot-1",
      toolHint: null,
    });
  });

  it("收到 quota_exhausted 後把 assistant 訊息換成固定文案並標記，done 後結束串流", async () => {
    emit([
      { type: "status", status: "react_thinking" },
      { type: "quota_exhausted", content: "本月額度已用完，請聯繫管理員" },
      { type: "done" },
    ]);
    const { result } = renderHook(() => useStreaming());

    await act(async () => {
      await result.current.sendMessage("你好");
    });

    const { messages, isStreaming, toolHint } = useChatStore.getState();
    expect(messages).toHaveLength(2);
    expect(messages[0]).toMatchObject({ role: "user", content: "你好" });
    expect(messages[1]).toMatchObject({
      role: "assistant",
      content: "本月額度已用完，請聯繫管理員",
      quotaExhausted: true,
    });
    expect(messages[1].content).not.toMatch(/⚠️/);
    expect(isStreaming).toBe(false);
    expect(toolHint).toBeNull();
  });

  it("quota_exhausted 缺 content 時使用預設文案", async () => {
    emit([{ type: "quota_exhausted" }, { type: "done" }]);
    const { result } = renderHook(() => useStreaming());

    await act(async () => {
      await result.current.sendMessage("hi");
    });

    const last = useChatStore.getState().messages.at(-1);
    expect(last).toMatchObject({
      role: "assistant",
      content: "本月額度已用完，服務暫停，請聯繫管理員。",
      quotaExhausted: true,
    });
  });

  it("一般 error 事件仍走 ⚠️ 通用錯誤路徑，不標記 quotaExhausted", async () => {
    emit([{ type: "error", message: "後端爆炸" }, { type: "done" }]);
    const { result } = renderHook(() => useStreaming());

    await act(async () => {
      await result.current.sendMessage("hi");
    });

    const last = useChatStore.getState().messages.at(-1);
    expect(last?.content).toBe("⚠️ 後端爆炸");
    expect(last?.quotaExhausted).toBeUndefined();
  });
});
