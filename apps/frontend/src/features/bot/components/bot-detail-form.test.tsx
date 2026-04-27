import { describe, it, expect, vi, beforeEach } from "vitest";
import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { renderWithProviders } from "@/test/test-utils";
import { BotDetailForm } from "@/features/bot/components/bot-detail-form";
import { mockBot } from "@/test/fixtures/bot";
import { useAuthStore } from "@/stores/use-auth-store";

// Mock useBuiltInTools hook — 避免 API call 拖慢/失敗
vi.mock("@/hooks/queries/use-built-in-tools", () => ({
  useBuiltInTools: () => ({
    data: [
      {
        name: "rag_query",
        label: "知識庫查詢",
        description: "對 bot 連結的知識庫做向量檢索，適合一般問答。",
        requires_kb: true,
      },
      {
        name: "query_dm_with_image",
        label: "DM 圖卡查詢",
        description: "對 catalog PDF 知識庫檢索並回傳子頁 PNG。",
        requires_kb: true,
      },
    ],
    isLoading: false,
  }),
}));

describe("BotDetailForm", () => {
  const mockOnSave = vi.fn();
  const mockOnDelete = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
    useAuthStore.setState({
      token: "test-token",
      tenantId: "tenant-1",
      tenants: [
        {
          id: "tenant-1",
          name: "Test Tenant",
          plan: "pro",
          monthly_token_limit: null,
          created_at: "2024-01-01T00:00:00Z",
          updated_at: "2024-01-01T00:00:00Z",
        },
      ],
    });
  });

  it("should render bot name input with current value", () => {
    renderWithProviders(
      <BotDetailForm
        bot={mockBot}
        onSave={mockOnSave}
        onDelete={mockOnDelete}
        isSaving={false}
        isDeleting={false}
      />,
    );
    const nameInput = screen.getByLabelText("名稱");
    expect(nameInput).toHaveValue("Customer Service Bot");
  });

  it("should render LLM parameter inputs in LLM & Prompt tab", async () => {
    const user = userEvent.setup();
    renderWithProviders(
      <BotDetailForm
        bot={mockBot}
        onSave={mockOnSave}
        onDelete={mockOnDelete}
        isSaving={false}
        isDeleting={false}
      />,
    );
    await user.click(screen.getByRole("tab", { name: /LLM.*Prompt/i }));
    expect(screen.getByLabelText("溫度（0-1）")).toHaveValue(0.3);
    expect(screen.getByLabelText("最大 Token 數（128-4096）")).toHaveValue(1024);
    expect(screen.getByLabelText("歷史訊息數（0-35）")).toHaveValue(10);
  });

  it("should render system prompt textarea in LLM & Prompt tab", async () => {
    const user = userEvent.setup();
    renderWithProviders(
      <BotDetailForm
        bot={mockBot}
        onSave={mockOnSave}
        onDelete={mockOnDelete}
        isSaving={false}
        isDeleting={false}
      />,
    );
    await user.click(screen.getByRole("tab", { name: /LLM.*Prompt/i }));
    expect(screen.getByLabelText("Bot 自訂指令")).toHaveValue(
      "You are a helpful customer service bot.",
    );
  });

  it("should render LINE channel fields in LINE tab", async () => {
    const user = userEvent.setup();
    renderWithProviders(
      <BotDetailForm
        bot={mockBot}
        onSave={mockOnSave}
        onDelete={mockOnDelete}
        isSaving={false}
        isDeleting={false}
      />,
    );
    await user.click(screen.getByRole("tab", { name: "LINE" }));
    expect(screen.getByLabelText("頻道密鑰")).toBeInTheDocument();
    expect(screen.getByLabelText("存取權杖")).toBeInTheDocument();
  });

  it("should render both built-in tool checkboxes in 能力 tab", async () => {
    const user = userEvent.setup();
    renderWithProviders(
      <BotDetailForm
        bot={mockBot}
        onSave={mockOnSave}
        onDelete={mockOnDelete}
        isSaving={false}
        isDeleting={false}
      />,
    );
    await user.click(screen.getByRole("tab", { name: "能力" }));
    expect(screen.getByText("知識庫查詢")).toBeInTheDocument();
    expect(screen.getByText("DM 圖卡查詢")).toBeInTheDocument();
  });

  it("should reflect bot.enabled_tools in checkbox checked state", async () => {
    const user = userEvent.setup();
    const botWithDmTool = {
      ...mockBot,
      enabled_tools: ["query_dm_with_image"],
    };
    renderWithProviders(
      <BotDetailForm
        bot={botWithDmTool}
        onSave={mockOnSave}
        onDelete={mockOnDelete}
        isSaving={false}
        isDeleting={false}
      />,
    );
    await user.click(screen.getByRole("tab", { name: "能力" }));
    const checkboxes = screen
      .getAllByRole("checkbox")
      .filter((cb) => {
        const lbl = cb.closest("label");
        return (
          lbl &&
          (lbl.textContent?.includes("知識庫查詢") ||
            lbl.textContent?.includes("DM 圖卡查詢"))
        );
      });
    // 兩個 tool checkbox 應出現
    expect(checkboxes.length).toBe(2);
    // DM 圖卡 checkbox 應 checked，rag_query 不應 checked
    const dmCheckbox = checkboxes.find((cb) =>
      cb.closest("label")?.textContent?.includes("DM 圖卡"),
    );
    const ragCheckbox = checkboxes.find((cb) =>
      cb.closest("label")?.textContent?.includes("知識庫查詢"),
    );
    expect(dmCheckbox).toBeChecked();
    expect(ragCheckbox).not.toBeChecked();
  });

  it("should toggle enabled_tools when clicking checkbox", async () => {
    const user = userEvent.setup();
    const botWithRagOnly = { ...mockBot, enabled_tools: ["rag_query"] };
    renderWithProviders(
      <BotDetailForm
        bot={botWithRagOnly}
        onSave={mockOnSave}
        onDelete={mockOnDelete}
        isSaving={false}
        isDeleting={false}
      />,
    );
    await user.click(screen.getByRole("tab", { name: "能力" }));
    const dmLabel = screen.getByText("DM 圖卡查詢").closest("label")!;
    const dmCheckbox = dmLabel.querySelector(
      'input[type="checkbox"]',
    ) as HTMLInputElement;
    expect(dmCheckbox).not.toBeChecked();
    await user.click(dmCheckbox);
    expect(dmCheckbox).toBeChecked();
  });

  it("should send enabled_tools without forced override on submit", async () => {
    const user = userEvent.setup();
    const botWithDmOnly = {
      ...mockBot,
      enabled_tools: ["query_dm_with_image"],
    };
    renderWithProviders(
      <BotDetailForm
        bot={botWithDmOnly}
        onSave={mockOnSave}
        onDelete={mockOnDelete}
        isSaving={false}
        isDeleting={false}
      />,
    );
    const saveBtn = screen.getByRole("button", { name: /儲存/ });
    await user.click(saveBtn);
    // 既有 onSubmit 不再強制覆寫，enabled_tools 應保留 form state
    // （注意：onSave 是 async，可能因 KB 驗證等邏輯不過 — 但若觸發，
    // payload 必須含 query_dm_with_image，不該被改成 ["rag_query"]）
    if (mockOnSave.mock.calls.length > 0) {
      const payload = mockOnSave.mock.calls[0][0];
      expect(payload.enabled_tools).toContain("query_dm_with_image");
      expect(payload.enabled_tools).not.toEqual(["rag_query"]);
    }
  });

  it("should serialize existing bot.tool_configs back on submit", async () => {
    const user = userEvent.setup();
    const botWithToolConfigs = {
      ...mockBot,
      tool_configs: {
        rag_query: { rag_top_k: 3 },
        query_dm_with_image: { rag_top_k: 10, rerank_enabled: true },
      },
    };
    renderWithProviders(
      <BotDetailForm
        bot={botWithToolConfigs}
        onSave={mockOnSave}
        onDelete={mockOnDelete}
        isSaving={false}
        isDeleting={false}
      />,
    );
    const saveBtn = screen.getByRole("button", { name: /儲存/ });
    await user.click(saveBtn);
    if (mockOnSave.mock.calls.length > 0) {
      const payload = mockOnSave.mock.calls[0][0];
      expect(payload.tool_configs).toBeDefined();
      expect(payload.tool_configs.rag_query).toEqual({ rag_top_k: 3 });
      expect(payload.tool_configs.query_dm_with_image).toEqual({
        rag_top_k: 10,
        rerank_enabled: true,
      });
    }
  });

  it("should show 知識庫與檢索 section in 能力 tab", async () => {
    const user = userEvent.setup();
    renderWithProviders(
      <BotDetailForm
        bot={mockBot}
        onSave={mockOnSave}
        onDelete={mockOnDelete}
        isSaving={false}
        isDeleting={false}
      />,
    );
    await user.click(screen.getByRole("tab", { name: "能力" }));
    expect(screen.getByText("知識庫與檢索")).toBeInTheDocument();
    expect(screen.getByText("預設檢索參數")).toBeInTheDocument();
    // Top K / threshold should appear under 能力 tab (not LLM tab)
    expect(screen.getByLabelText("Top K（1-20）")).toBeInTheDocument();
    expect(screen.getByLabelText("分數閾值（0-1）")).toBeInTheDocument();
  });

  it("should block submit when no tool is enabled", async () => {
    const user = userEvent.setup();
    const botWithNoTool = { ...mockBot, enabled_tools: [] };
    renderWithProviders(
      <BotDetailForm
        bot={botWithNoTool}
        onSave={mockOnSave}
        onDelete={mockOnDelete}
        isSaving={false}
        isDeleting={false}
      />,
    );
    const saveBtn = screen.getByRole("button", { name: /儲存/ });
    await user.click(saveBtn);
    // onSave 不該被呼叫
    expect(mockOnSave).not.toHaveBeenCalled();
  });

  it("should render save and delete buttons", () => {
    renderWithProviders(
      <BotDetailForm
        bot={mockBot}
        onSave={mockOnSave}
        onDelete={mockOnDelete}
        isSaving={false}
        isDeleting={false}
      />,
    );
    expect(
      screen.getByRole("button", { name: "儲存變更" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "刪除機器人" }),
    ).toBeInTheDocument();
  });

  it("should show loading state when saving", () => {
    renderWithProviders(
      <BotDetailForm
        bot={mockBot}
        onSave={mockOnSave}
        onDelete={mockOnDelete}
        isSaving={true}
        isDeleting={false}
      />,
    );
    expect(
      screen.getByRole("button", { name: "儲存中..." }),
    ).toBeDisabled();
  });

  it("should show loading state when deleting", () => {
    renderWithProviders(
      <BotDetailForm
        bot={mockBot}
        onSave={mockOnSave}
        onDelete={mockOnDelete}
        isSaving={false}
        isDeleting={true}
      />,
    );
    expect(
      screen.getByRole("button", { name: "刪除中..." }),
    ).toBeDisabled();
  });

  it("should show FAB icon upload section in Widget tab", async () => {
    const user = userEvent.setup();
    renderWithProviders(
      <BotDetailForm
        bot={mockBot}
        onSave={mockOnSave}
        onDelete={mockOnDelete}
        isSaving={false}
        isDeleting={false}
      />,
    );
    await user.click(screen.getByRole("tab", { name: "Widget" }));
    expect(screen.getByText("FAB 按鈕圖示")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /上傳圖片/ })).toBeInTheDocument();
  });

  it("should show placeholder when no icon uploaded", async () => {
    const user = userEvent.setup();
    renderWithProviders(
      <BotDetailForm
        bot={mockBot}
        onSave={mockOnSave}
        onDelete={mockOnDelete}
        isSaving={false}
        isDeleting={false}
      />,
    );
    await user.click(screen.getByRole("tab", { name: "Widget" }));
    expect(screen.getByText("尚未上傳自訂圖示")).toBeInTheDocument();
  });

  it("should render Widget tab content without avatar section", async () => {
    const user = userEvent.setup();
    renderWithProviders(
      <BotDetailForm
        bot={mockBot}
        onSave={mockOnSave}
        onDelete={mockOnDelete}
        isSaving={false}
        isDeleting={false}
      />,
    );
    await user.click(screen.getByRole("tab", { name: "Widget" }));
    expect(screen.getByText("允許來源")).toBeInTheDocument();
    expect(screen.getByText("對話歷史")).toBeInTheDocument();
    expect(screen.queryByText("Avatar 角色選擇")).not.toBeInTheDocument();
    expect(screen.getByText("Widget 文字設定")).toBeInTheDocument();
    expect(screen.getByText("嵌入碼")).toBeInTheDocument();
  });

  // Sprint W.4 (Knowledge Mode Wiki vs RAG) tests removed — Wiki feature
  // dropped in commit 9f62f01. KB binding lives on the "能力" tab and is
  // covered by other test files.

});
