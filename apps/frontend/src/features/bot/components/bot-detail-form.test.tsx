import { describe, it, expect, vi, beforeEach } from "vitest";
import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { renderWithProviders } from "@/test/test-utils";
import { BotDetailForm } from "@/features/bot/components/bot-detail-form";
import { mockBot } from "@/test/fixtures/bot";
import { useAuthStore } from "@/stores/use-auth-store";
import type { StructuredOutputCapability } from "@/types/llm-capability";

// Issue #70 — 能力等級 hook 以 vi.mock 隔離，各測試自行指定 tier
const { mockCapability } = vi.hoisted(() => ({ mockCapability: vi.fn() }));

vi.mock("@/hooks/queries/use-structured-output-capability", () => ({
  useStructuredOutputCapability: (provider?: string, model?: string) =>
    mockCapability(provider, model),
}));

function capabilityResult(
  tier: StructuredOutputCapability["tier"],
  note = "",
) {
  return {
    data: { provider: "openai", model: "gpt-5", tier, note },
    isLoading: false,
    isError: false,
  };
}

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
    mockCapability.mockReturnValue({
      data: undefined,
      isLoading: false,
      isError: false,
    });
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

  // Issue #66 — 推理模式（fast / deep）
  describe("mode (Issue #66)", () => {
    it("should default to deep and hide the fast hint", () => {
      renderWithProviders(
        <BotDetailForm
          bot={mockBot}
          onSave={mockOnSave}
          onDelete={mockOnDelete}
          isSaving={false}
          isDeleting={false}
        />,
      );
      expect(screen.getByRole("radio", { name: /深度道（deep）/ })).toBeChecked();
      expect(screen.getByRole("radio", { name: /快速道（fast）/ })).not.toBeChecked();
      expect(
        screen.queryByText("快速道模式下 rerank / 查詢改寫 / HyDE 會自動關閉"),
      ).not.toBeInTheDocument();
    });

    it("should reflect bot.mode = fast and show the fast hint", () => {
      renderWithProviders(
        <BotDetailForm
          bot={{ ...mockBot, mode: "fast" }}
          onSave={mockOnSave}
          onDelete={mockOnDelete}
          isSaving={false}
          isDeleting={false}
        />,
      );
      expect(screen.getByRole("radio", { name: /快速道（fast）/ })).toBeChecked();
      expect(
        screen.getByText("快速道模式下 rerank / 查詢改寫 / HyDE 會自動關閉"),
      ).toBeInTheDocument();
    });

    it("should show the fast hint after selecting fast", async () => {
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
      await user.click(screen.getByRole("radio", { name: /快速道（fast）/ }));
      expect(
        screen.getByText("快速道模式下 rerank / 查詢改寫 / HyDE 會自動關閉"),
      ).toBeInTheDocument();
    });

    it("should include selected mode in submitted payload", async () => {
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
      await user.click(screen.getByRole("radio", { name: /快速道（fast）/ }));
      await user.click(screen.getByRole("button", { name: /儲存/ }));
      expect(mockOnSave).toHaveBeenCalledTimes(1);
      expect(mockOnSave.mock.calls[0][0].mode).toBe("fast");
    });
  });

  // Sprint W.4 (Knowledge Mode Wiki vs RAG) tests removed — Wiki feature
  // dropped in commit 9f62f01. KB binding lives on the "能力" tab and is
  // covered by other test files.

  // Issue #70 — 知識庫問答模式 + 輸出格式 + 能力等級提示
  describe("kb mode & output format (Issue #70)", () => {
    const renderForm = (bot = mockBot) =>
      renderWithProviders(
        <BotDetailForm
          bot={bot}
          onSave={mockOnSave}
          onDelete={mockOnDelete}
          isSaving={false}
          isDeleting={false}
        />,
      );

    it("should offer 知識庫問答 option and only show 未命中話術 for kb", async () => {
      const user = userEvent.setup();
      renderForm();
      const kbRadio = screen.getByRole("radio", { name: /知識庫問答（kb）/ });
      expect(kbRadio).not.toBeChecked();
      expect(screen.queryByLabelText("未命中話術")).not.toBeInTheDocument();
      await user.click(kbRadio);
      expect(kbRadio).toBeChecked();
      const missReply = screen.getByLabelText("未命中話術");
      expect(missReply).toHaveAttribute(
        "placeholder",
        "很抱歉，這個問題不在我的服務範圍內，歡迎換個方式問我。",
      );
      await user.click(screen.getByRole("radio", { name: /深度道（deep）/ }));
      expect(screen.queryByLabelText("未命中話術")).not.toBeInTheDocument();
    });

    it("should reflect bot.mode = kb and miss_reply from server", () => {
      renderForm({ ...mockBot, mode: "kb", miss_reply: "請洽客服" });
      expect(screen.getByRole("radio", { name: /知識庫問答（kb）/ })).toBeChecked();
      expect(screen.getByLabelText("未命中話術")).toHaveValue("請洽客服");
    });

    it("should default output_format to text and show schema textarea only for json", async () => {
      const user = userEvent.setup();
      renderForm();
      expect(screen.getByRole("radio", { name: /^一般/ })).toBeChecked();
      expect(screen.queryByLabelText("JSON schema（選填）")).not.toBeInTheDocument();
      await user.click(screen.getByRole("radio", { name: /^JSON/ }));
      expect(screen.getByLabelText("JSON schema（選填）")).toBeInTheDocument();
      await user.click(screen.getByRole("radio", { name: /純文字/ }));
      expect(screen.queryByLabelText("JSON schema（選填）")).not.toBeInTheDocument();
    });

    it("should prefill schema textarea from bot.output_schema", async () => {
      renderForm({
        ...mockBot,
        output_format: "json",
        output_schema: { type: "object" },
      });
      expect(screen.getByRole("radio", { name: /^JSON/ })).toBeChecked();
      expect(screen.getByLabelText("JSON schema（選填）")).toHaveValue(
        JSON.stringify({ type: "object" }, null, 2),
      );
    });

    it("should block submit when JSON schema is not a valid JSON object", async () => {
      const user = userEvent.setup();
      renderForm();
      await user.click(screen.getByRole("radio", { name: /^JSON/ }));
      const schemaInput = screen.getByLabelText("JSON schema（選填）");
      await user.click(schemaInput);
      await user.paste("{not json");
      await user.click(screen.getByRole("button", { name: /儲存/ }));
      expect(
        await screen.findByText("JSON schema 必須是合法的 JSON 物件"),
      ).toBeInTheDocument();
      expect(mockOnSave).not.toHaveBeenCalled();
    });

    it("should block submit when JSON schema parses to a non-object", async () => {
      const user = userEvent.setup();
      renderForm();
      await user.click(screen.getByRole("radio", { name: /^JSON/ }));
      await user.click(screen.getByLabelText("JSON schema（選填）"));
      await user.paste("[1, 2]");
      await user.click(screen.getByRole("button", { name: /儲存/ }));
      expect(
        await screen.findByText("JSON schema 必須是合法的 JSON 物件"),
      ).toBeInTheDocument();
      expect(mockOnSave).not.toHaveBeenCalled();
    });

    it("should include mode / output_format / output_schema / miss_reply in payload", async () => {
      const user = userEvent.setup();
      mockCapability.mockReturnValue(capabilityResult("native_schema"));
      renderForm();
      await user.click(screen.getByRole("radio", { name: /知識庫問答（kb）/ }));
      await user.click(screen.getByRole("radio", { name: /^JSON/ }));
      await user.click(screen.getByLabelText("未命中話術"));
      await user.paste('{"status":"out_of_scope"}');
      await user.click(screen.getByLabelText("JSON schema（選填）"));
      await user.paste('{"type":"object","required":["answer"]}');
      await user.click(screen.getByRole("button", { name: /儲存/ }));
      expect(mockOnSave).toHaveBeenCalledTimes(1);
      const payload = mockOnSave.mock.calls[0][0];
      expect(payload.mode).toBe("kb");
      expect(payload.output_format).toBe("json");
      expect(payload.output_schema).toEqual({
        type: "object",
        required: ["answer"],
      });
      expect(payload.miss_reply).toBe('{"status":"out_of_scope"}');
      expect(payload).not.toHaveProperty("output_schema_text");
    });

    it("should send output_schema null when schema is empty or format is not json", async () => {
      const user = userEvent.setup();
      renderForm();
      await user.click(screen.getByRole("radio", { name: /純文字/ }));
      await user.click(screen.getByRole("button", { name: /儲存/ }));
      expect(mockOnSave).toHaveBeenCalledTimes(1);
      const payload = mockOnSave.mock.calls[0][0];
      expect(payload.output_format).toBe("plain_text");
      expect(payload.output_schema).toBeNull();
      expect(payload.miss_reply).toBe("");
      expect(payload.mode).toBe("deep");
    });

    it("should switch 未命中話術 placeholder / helper text when output_format is json", async () => {
      const user = userEvent.setup();
      renderForm({ ...mockBot, mode: "kb" });
      await user.click(screen.getByRole("radio", { name: /^JSON/ }));
      expect(screen.getByLabelText("未命中話術")).toHaveAttribute(
        "placeholder",
        '{"status":"out_of_scope","category":"unclassified","answer":""}',
      );
      expect(
        screen.getByText("JSON 輸出時話術本身必須是合法 JSON（留空用系統預設）"),
      ).toBeInTheDocument();
    });

    it("should block submit when output_format is json and miss_reply is not valid JSON", async () => {
      const user = userEvent.setup();
      renderForm({ ...mockBot, mode: "kb" });
      await user.click(screen.getByRole("radio", { name: /^JSON/ }));
      await user.click(screen.getByLabelText("未命中話術"));
      await user.paste("不是 JSON");
      await user.click(screen.getByRole("button", { name: /儲存/ }));
      expect(await screen.findByText("必須是合法 JSON")).toBeInTheDocument();
      expect(mockOnSave).not.toHaveBeenCalled();
    });

    it("should allow empty miss_reply with json output_format", async () => {
      const user = userEvent.setup();
      renderForm({ ...mockBot, mode: "kb" });
      await user.click(screen.getByRole("radio", { name: /^JSON/ }));
      await user.click(screen.getByRole("button", { name: /儲存/ }));
      expect(mockOnSave).toHaveBeenCalledTimes(1);
      expect(mockOnSave.mock.calls[0][0].miss_reply).toBe("");
    });

    describe("schema templates & display field", () => {
      const THREE_WAY_SCHEMA = {
        type: "object",
        additionalProperties: false,
        required: ["status", "category", "answer"],
        properties: {
          status: { type: "string", enum: ["km", "out_of_scope"] },
          category: {
            type: "string",
            enum: ["product-exhibit", "marketing", "store-ops", "unclassified"],
          },
          answer: { type: "string" },
        },
      };

      it("should fill the schema textarea with the selected template and parse it on save", async () => {
        const user = userEvent.setup();
        renderForm();
        await user.click(screen.getByRole("radio", { name: /^JSON/ }));
        expect(screen.getByLabelText("JSON schema（選填）")).toHaveValue("");
        await user.selectOptions(
          screen.getByLabelText("範本"),
          "三分流（status / category / answer）",
        );
        await user.click(screen.getByRole("button", { name: "套用範本" }));
        const textarea = screen.getByLabelText("JSON schema（選填）");
        expect(JSON.parse((textarea as HTMLTextAreaElement).value)).toEqual(
          THREE_WAY_SCHEMA,
        );
        expect(
          screen.getByText("必填欄位與 enum 都在 schema 裡定義，供應商依能力等級強制或驗證"),
        ).toBeInTheDocument();
        await user.click(screen.getByRole("button", { name: /儲存/ }));
        expect(mockOnSave).toHaveBeenCalledTimes(1);
        expect(mockOnSave.mock.calls[0][0].output_schema).toEqual(THREE_WAY_SCHEMA);
      });

      it("should show 通路顯示欄位 as a plain input when schema has no properties", async () => {
        const user = userEvent.setup();
        renderForm();
        expect(screen.queryByLabelText("通路顯示欄位")).not.toBeInTheDocument();
        await user.click(screen.getByRole("radio", { name: /^JSON/ }));
        const field = screen.getByLabelText("通路顯示欄位");
        expect(field.tagName).toBe("INPUT");
        expect(field).toHaveValue("answer");
        expect(
          screen.getByText("LINE / widget 等純文字通路顯示此欄位的內容；API 回完整 JSON"),
        ).toBeInTheDocument();
      });

      it("should offer schema property names as select options and default to answer", async () => {
        const user = userEvent.setup();
        renderForm();
        await user.click(screen.getByRole("radio", { name: /^JSON/ }));
        await user.click(screen.getByRole("button", { name: "套用範本" }));
        const select = screen.getByLabelText("通路顯示欄位");
        expect(select.tagName).toBe("SELECT");
        expect(
          screen.getAllByRole("option").filter((o) => o.closest("select") === select)
            .map((o) => o.textContent),
        ).toEqual(["status", "category", "answer"]);
        expect(select).toHaveValue("answer");
      });

      it("should fall back to the first property when schema has no answer", async () => {
        const user = userEvent.setup();
        renderForm();
        await user.click(screen.getByRole("radio", { name: /^JSON/ }));
        await user.click(screen.getByLabelText("JSON schema（選填）"));
        await user.paste('{"type":"object","properties":{"reply":{"type":"string"},"score":{"type":"number"}}}');
        await waitFor(() =>
          expect(screen.getByLabelText("通路顯示欄位")).toHaveValue("reply"),
        );
      });

      it("should include the chosen output_text_field in the payload", async () => {
        const user = userEvent.setup();
        renderForm();
        await user.click(screen.getByRole("radio", { name: /^JSON/ }));
        await user.click(screen.getByRole("button", { name: "套用範本" }));
        await user.selectOptions(screen.getByLabelText("通路顯示欄位"), "category");
        await user.click(screen.getByRole("button", { name: /儲存/ }));
        expect(mockOnSave).toHaveBeenCalledTimes(1);
        expect(mockOnSave.mock.calls[0][0].output_text_field).toBe("category");
      });

      it("should prefill output_text_field from the bot", async () => {
        const user = userEvent.setup();
        renderForm({
          ...mockBot,
          output_format: "json",
          output_schema: THREE_WAY_SCHEMA,
          output_text_field: "status",
        });
        expect(screen.getByLabelText("通路顯示欄位")).toHaveValue("status");
        await user.click(screen.getByRole("button", { name: /儲存/ }));
        expect(mockOnSave.mock.calls[0][0].output_text_field).toBe("status");
      });
    });

    describe("kb threshold hint", () => {
      const HINT =
        "知識庫問答模式建議 0.5 以上（Milvus COSINE 相似度 0–1，預設 0.3 偏鬆）；低於門檻直接回未命中話術，不會升級";

      it("should not show the hint for non-kb modes", async () => {
        const user = userEvent.setup();
        renderForm();
        await user.click(screen.getByRole("tab", { name: "能力" }));
        expect(screen.queryByText(HINT)).not.toBeInTheDocument();
      });

      it("should show the hint in amber when kb threshold is below 0.5", async () => {
        const user = userEvent.setup();
        renderForm({ ...mockBot, mode: "kb", rag_score_threshold: 0.3 });
        await user.click(screen.getByRole("tab", { name: "能力" }));
        const hint = screen.getByText(HINT);
        // data-tone 是唯一可觀察的語氣標記（顏色屬樣式），故以 testid/attr 驗證
        expect(hint).toHaveAttribute("data-tone", "warning");
        expect(hint.className).toContain("text-amber");
      });

      it("should show the hint in neutral tone when kb threshold is >= 0.5", async () => {
        const user = userEvent.setup();
        renderForm({ ...mockBot, mode: "kb", rag_score_threshold: 0.6 });
        await user.click(screen.getByRole("tab", { name: "能力" }));
        const hint = screen.getByText(HINT);
        expect(hint).toHaveAttribute("data-tone", "info");
        expect(hint.className).not.toContain("text-amber");
      });

      it("should not block submit when kb threshold is below 0.5", async () => {
        const user = userEvent.setup();
        renderForm({ ...mockBot, mode: "kb", rag_score_threshold: 0.3 });
        await user.click(screen.getByRole("button", { name: /儲存/ }));
        expect(mockOnSave).toHaveBeenCalledTimes(1);
        expect(mockOnSave.mock.calls[0][0].rag_score_threshold).toBe(0.3);
      });
    });

    describe("capability badge", () => {
      const openJson = async (user: ReturnType<typeof userEvent.setup>) => {
        await user.click(screen.getByRole("radio", { name: /^JSON/ }));
        return screen.getByRole("status", { name: "結構化輸出能力" });
      };

      it("should query the hook with the form's current provider/model", async () => {
        const user = userEvent.setup();
        mockCapability.mockReturnValue(capabilityResult("native_schema"));
        renderForm();
        await openJson(user);
        expect(mockCapability).toHaveBeenCalledWith("openai", "gpt-5");
      });

      it("should render green 原生 schema badge with note for native_schema", async () => {
        const user = userEvent.setup();
        mockCapability.mockReturnValue(
          capabilityResult("native_schema", "OpenAI response_format json_schema"),
        );
        renderForm();
        const badge = await openJson(user);
        expect(badge).toHaveTextContent("原生 schema");
        expect(badge.className).toContain("emerald");
        expect(
          screen.getByText("OpenAI response_format json_schema"),
        ).toBeInTheDocument();
      });

      it("should render amber badge for json_object", async () => {
        const user = userEvent.setup();
        mockCapability.mockReturnValue(capabilityResult("json_object"));
        renderForm();
        const badge = await openJson(user);
        expect(badge).toHaveTextContent("僅保證 JSON，欄位由系統驗證並重試一次");
        expect(badge.className).toContain("amber");
      });

      it("should render red badge for prompt_only", async () => {
        const user = userEvent.setup();
        mockCapability.mockReturnValue(capabilityResult("prompt_only"));
        renderForm();
        const badge = await openJson(user);
        expect(badge).toHaveTextContent("無格式保證，僅靠提示詞");
        expect(badge.className).toContain("red");
      });

      it("should render neutral 請先選擇模型 when provider/model are empty", async () => {
        const user = userEvent.setup();
        renderForm({ ...mockBot, llm_provider: "", llm_model: "" });
        const badge = await openJson(user);
        expect(badge).toHaveTextContent("請先選擇模型");
        expect(badge.className).not.toMatch(/emerald|amber|red/);
      });
    });
  });
});
