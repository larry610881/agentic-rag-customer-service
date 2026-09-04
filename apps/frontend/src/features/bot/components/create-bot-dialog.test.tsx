import { describe, it, expect, beforeEach, vi } from "vitest";
import { screen, waitFor } from "@testing-library/react";
import { renderWithProviders, userEvent } from "@/test/test-utils";
import { CreateBotDialog } from "@/features/bot/components/create-bot-dialog";
import { KB_QA_BOT_PRESET } from "@/features/bot/bot-presets";
import { useAuthStore } from "@/stores/use-auth-store";

const { mockMutate } = vi.hoisted(() => ({ mockMutate: vi.fn() }));

vi.mock("@/hooks/queries/use-bots", () => ({
  useCreateBot: () => ({ mutate: mockMutate, isPending: false }),
}));

describe("CreateBotDialog", () => {
  beforeEach(() => {
    mockMutate.mockClear();
    useAuthStore.setState({
      token: "test-token",
      tenantId: "tenant-1",
      tenants: [],
    });
  });

  it("should render create button", () => {
    renderWithProviders(<CreateBotDialog />);
    expect(
      screen.getByRole("button", { name: "建立機器人" }),
    ).toBeInTheDocument();
  });

  it("should open dialog on button click", async () => {
    const user = userEvent.setup();
    renderWithProviders(<CreateBotDialog />);
    await user.click(screen.getByRole("button", { name: "建立機器人" }));
    expect(screen.getByText("建立新的機器人來處理客戶對話。")).toBeInTheDocument();
  });

  it("should show validation error for empty name", async () => {
    const user = userEvent.setup();
    renderWithProviders(<CreateBotDialog />);
    await user.click(screen.getByRole("button", { name: "建立機器人" }));
    // 未輸入名稱直接送出
    await user.click(screen.getByRole("button", { name: "建立" }));
    await waitFor(() => {
      expect(screen.getByText("請輸入名稱")).toBeInTheDocument();
    });
  });

  // Issue #70 — 「知識庫問答」快速範本
  describe("preset (Issue #70)", () => {
    it("should default to 一般客服 and send only name/description", async () => {
      const user = userEvent.setup();
      renderWithProviders(<CreateBotDialog />);
      await user.click(screen.getByRole("button", { name: "建立機器人" }));
      expect(screen.getByRole("radio", { name: /一般客服/ })).toBeChecked();
      await user.type(screen.getByLabelText("名稱"), "一般 bot");
      await user.click(screen.getByRole("button", { name: "建立" }));
      await waitFor(() => expect(mockMutate).toHaveBeenCalledTimes(1));
      const payload = mockMutate.mock.calls[0][0];
      expect(payload.name).toBe("一般 bot");
      expect(payload).not.toHaveProperty("mode");
      expect(payload).not.toHaveProperty("output_format");
    });

    it("should apply the 知識庫問答 preset to the create payload", async () => {
      const user = userEvent.setup();
      renderWithProviders(<CreateBotDialog />);
      await user.click(screen.getByRole("button", { name: "建立機器人" }));
      await user.type(screen.getByLabelText("名稱"), "3D 展 KB bot");
      await user.click(screen.getByRole("radio", { name: /知識庫問答/ }));
      await user.click(screen.getByRole("button", { name: "建立" }));
      await waitFor(() => expect(mockMutate).toHaveBeenCalledTimes(1));
      const payload = mockMutate.mock.calls[0][0];
      expect(payload).toMatchObject({
        name: "3D 展 KB bot",
        mode: "kb",
        enabled_tools: ["rag_query"],
        memory_enabled: false,
        rerank_enabled: false,
        output_format: "plain_text",
        show_sources: true,
        rag_score_threshold: 0.5,
      });
      expect(payload).toMatchObject(KB_QA_BOT_PRESET);
    });
  });
});
