import { render, screen, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { ConfigSnapshotRecord } from "@/types/config-snapshot";
import { ConfigSnapshotPanel } from "./config-snapshot-panel";

vi.mock("@/hooks/queries/use-config-snapshots", () => ({
  useConfigSnapshot: vi.fn(),
}));
vi.mock("sonner", () => ({ toast: { success: vi.fn(), error: vi.fn() } }));

import { useConfigSnapshot } from "@/hooks/queries/use-config-snapshots";
const useConfigSnapshotMock = vi.mocked(useConfigSnapshot);

const HASH = "0123456789abcdef0123456789abcdef";

const RECORD: ConfigSnapshotRecord = {
  hash: HASH,
  schema: 1,
  first_seen_at: "2026-09-01T10:00:00Z",
  snapshot: {
    schema: 1,
    channel: "line",
    bot_id: "bot-1",
    system_prompt: "你是家樂福客服",
    platform_prompt_fallback: true,
    worker_name: "faq_worker",
    llm_provider: "openai",
    llm_model: "gpt-4o-mini",
    router_model: "gpt-4o-mini",
    llm_params: { temperature: 0.2, max_tokens: 1024 },
    retrieval: {
      modes: ["vector", "keyword"],
      rerank_enabled: true,
      rerank_model: "bge-reranker",
      rerank_top_n: 5,
      kb_ids: ["kb-1", "kb-2"],
      direct_retrieval: false,
    },
    enabled_tools: ["search_kb", "get_order"],
    max_tool_calls: 3,
    guard: {
      input_rules: [
        { id: "role_hijack", pattern: "(?i)ignore previous", enabled: true },
        { id: "sql", pattern: "drop table", enabled: false },
      ],
      output_keywords: ["密碼"],
      blocked_response: "抱歉，無法協助此請求",
      llm_guard_enabled: true,
      llm_input_guard_enabled: false,
    },
    memory_enabled: true,
    extra: { fast_path: "on" },
  },
};

function mockQuery(state: Partial<ReturnType<typeof useConfigSnapshot>>) {
  useConfigSnapshotMock.mockReturnValue({
    data: undefined,
    isLoading: false,
    error: null,
    ...state,
  } as unknown as ReturnType<typeof useConfigSnapshot>);
}

describe("ConfigSnapshotPanel", () => {
  beforeEach(() => {
    useConfigSnapshotMock.mockReset();
  });

  it("載入中顯示 skeleton", () => {
    mockQuery({ isLoading: true });
    render(<ConfigSnapshotPanel hash={HASH} />);
    expect(screen.getByTestId("snapshot-loading")).toBeInTheDocument();
  });

  it("錯誤時顯示訊息", () => {
    mockQuery({ error: new Error("boom") });
    render(<ConfigSnapshotPanel hash={HASH} />);
    expect(screen.getByTestId("snapshot-error")).toHaveTextContent("boom");
  });

  it("渲染 hash（前 12 碼、hover 全文）與六個分組", () => {
    mockQuery({ data: RECORD });
    render(<ConfigSnapshotPanel hash={HASH} />);

    const chip = screen.getByTestId("config-hash-chip");
    expect(chip).toHaveTextContent(HASH.slice(0, 12));
    expect(chip).toHaveAttribute("title", HASH);
    expect(screen.getByRole("button", { name: "複製 hash" })).toBeInTheDocument();

    // 提示詞
    const prompt = screen.getByTestId("snapshot-section-prompt");
    expect(within(prompt).getByTestId("snapshot-system-prompt")).toHaveTextContent(
      "你是家樂福客服",
    );
    expect(within(prompt).getByText("使用平台預設提示詞")).toBeInTheDocument();
    expect(within(prompt).getByText("worker: faq_worker")).toBeInTheDocument();

    // 模型與參數
    const model = screen.getByTestId("snapshot-section-model");
    // llm_model 與 router_model 皆為 gpt-4o-mini → 兩處
    expect(within(model).getAllByText("gpt-4o-mini")).toHaveLength(2);
    expect(within(model).getByText("openai")).toBeInTheDocument();
    expect(within(model).getByText("temperature")).toBeInTheDocument();
    expect(within(model).getByText("0.2")).toBeInTheDocument();

    // 檢索
    const retrieval = screen.getByTestId("snapshot-section-retrieval");
    expect(within(retrieval).getByText("vector")).toBeInTheDocument();
    expect(within(retrieval).getByText("kb-2")).toBeInTheDocument();
    expect(within(retrieval).getByText("bge-reranker")).toBeInTheDocument();

    // 工具
    const tools = screen.getByTestId("snapshot-section-tools");
    expect(within(tools).getByText("get_order")).toBeInTheDocument();
    expect(within(tools).getByText("3")).toBeInTheDocument();

    // 防護
    const guard = screen.getByTestId("snapshot-section-guard");
    expect(within(guard).getByText("2 條")).toBeInTheDocument();
    expect(within(guard).getByText("role_hijack")).toBeInTheDocument();
    expect(within(guard).getByText("drop table")).toBeInTheDocument();
    expect(within(guard).getByText("密碼")).toBeInTheDocument();
    expect(within(guard).getByText("抱歉，無法協助此請求")).toBeInTheDocument();

    // 記憶
    const memory = screen.getByTestId("snapshot-section-memory");
    expect(within(memory).getByText("啟用")).toBeInTheDocument();
    expect(within(memory).getByText("fast_path")).toBeInTheDocument();
  });

  it("guard 為 null 時顯示未啟用防護", () => {
    mockQuery({
      data: { ...RECORD, snapshot: { ...RECORD.snapshot, guard: null } },
    });
    render(<ConfigSnapshotPanel hash={HASH} />);
    expect(screen.getByText("此設定未啟用防護")).toBeInTheDocument();
  });
});
