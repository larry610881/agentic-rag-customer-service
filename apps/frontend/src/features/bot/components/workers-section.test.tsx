import { describe, it, expect, vi, beforeEach } from "vitest";
import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { renderWithProviders } from "@/test/test-utils";
import { WorkersSection } from "@/features/bot/components/workers-section";
import type { WorkerConfig } from "@/types/worker-config";

const mockWorker: WorkerConfig = {
  id: "worker-1",
  bot_id: "bot-1",
  name: "退貨客服",
  description: "客戶詢問退貨或退款",
  worker_prompt: "",
  llm_provider: null,
  llm_model: null,
  temperature: 0.7,
  max_tokens: 1024,
  max_tool_calls: 5,
  direct_retrieval: false,
  enabled_mcp_ids: [],
  knowledge_base_ids: [],
  enabled_tools: null,
  sort_order: 0,
  created_at: "2024-01-01T00:00:00Z",
  updated_at: "2024-01-01T00:00:00Z",
};

const createMutate = vi.fn();
const updateMutate = vi.fn();
const deleteMutate = vi.fn();
let workersData: WorkerConfig[] = [];

vi.mock("@/hooks/queries/use-workers", () => ({
  useWorkers: () => ({ data: workersData, isLoading: false }),
  useCreateWorker: () => ({ mutate: createMutate, isPending: false }),
  useUpdateWorker: () => ({ mutate: updateMutate, isPending: false }),
  useDeleteWorker: () => ({ mutate: deleteMutate, isPending: false }),
}));

vi.mock("@/hooks/queries/use-mcp-registry", () => ({
  useMcpRegistryAccessible: () => ({ data: [] }),
}));

describe("WorkersSection — Issue #66 快速道（direct_retrieval）", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    workersData = [mockWorker];
  });

  it("should render 快速道 switch reflecting worker.direct_retrieval", async () => {
    const user = userEvent.setup();
    renderWithProviders(<WorkersSection botId="bot-1" botTenantId="tenant-1" />);
    await user.click(screen.getByRole("button", { name: /退貨客服/ }));

    const sw = screen.getByRole("switch", { name: "快速道（直接檢索）" });
    expect(sw).toHaveAttribute("aria-checked", "false");
    expect(
      screen.getByText("常見問題直答，複雜問題自動升級完整推理"),
    ).toBeInTheDocument();
  });

  it("should render switch checked when direct_retrieval is true", async () => {
    const user = userEvent.setup();
    workersData = [{ ...mockWorker, direct_retrieval: true }];
    renderWithProviders(<WorkersSection botId="bot-1" botTenantId="tenant-1" />);
    await user.click(screen.getByRole("button", { name: /退貨客服/ }));

    expect(
      screen.getByRole("switch", { name: "快速道（直接檢索）" }),
    ).toHaveAttribute("aria-checked", "true");
  });

  it("should call update with direct_retrieval when switch toggled", async () => {
    const user = userEvent.setup();
    renderWithProviders(<WorkersSection botId="bot-1" botTenantId="tenant-1" />);
    await user.click(screen.getByRole("button", { name: /退貨客服/ }));
    await user.click(screen.getByRole("switch", { name: "快速道（直接檢索）" }));

    expect(updateMutate).toHaveBeenCalledTimes(1);
    expect(updateMutate).toHaveBeenCalledWith(
      { workerId: "worker-1", data: { direct_retrieval: true } },
      expect.anything(),
    );
  });

  it("should create worker with direct_retrieval false by default", async () => {
    const user = userEvent.setup();
    renderWithProviders(<WorkersSection botId="bot-1" botTenantId="tenant-1" />);
    await user.click(screen.getByRole("button", { name: /新增 Sub-agent/ }));

    expect(createMutate).toHaveBeenCalledWith(
      { name: "Sub-agent 2", direct_retrieval: false },
      expect.anything(),
    );
  });
});
