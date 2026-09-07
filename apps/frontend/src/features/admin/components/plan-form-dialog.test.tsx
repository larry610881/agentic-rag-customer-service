import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { PlanFormDialog } from "@/features/admin/components/plan-form-dialog";
import { renderWithProviders } from "@/test/test-utils";
import type { Plan } from "@/types/plan";

vi.mock("@/hooks/queries/use-plans", () => ({
  useCreatePlan: vi.fn(),
  useUpdatePlan: vi.fn(),
}));

vi.mock("@/hooks/queries/use-plan-multipliers", () => ({
  usePlanMultipliers: vi.fn(),
  useReplacePlanMultipliers: vi.fn(),
}));

import { useCreatePlan, useUpdatePlan } from "@/hooks/queries/use-plans";
import {
  usePlanMultipliers,
  useReplacePlanMultipliers,
} from "@/hooks/queries/use-plan-multipliers";

const createMock = vi.mocked(useCreatePlan);
const updateMock = vi.mocked(useUpdatePlan);
const multipliersMock = vi.mocked(usePlanMultipliers);
const replaceMock = vi.mocked(useReplacePlanMultipliers);

const createMutateAsync = vi.fn();
const updateMutateAsync = vi.fn();
const replaceMutateAsync = vi.fn();

const POINTS_PLAN: Plan = {
  id: "plan-pts",
  name: "pro-points",
  base_monthly_tokens: 10_000_000,
  addon_pack_tokens: 5_000_000,
  base_price: "1000",
  addon_price: "200",
  currency: "TWD",
  description: null,
  is_active: true,
  created_at: "2026-09-01T00:00:00Z",
  updated_at: "2026-09-01T00:00:00Z",
  billing_mode: "points",
  monthly_points: 5000,
  addon_pack_points: 1000,
  default_category_multiplier: 1,
  exhaustion_policy: "block",
  tenant_may_change_policy: true,
  auto_topup_monthly_cap: 2,
  grace_percent: 5,
  block_message: "額度用完",
};

describe("PlanFormDialog（Issue #74 計價 / 用盡策略）", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    createMutateAsync.mockResolvedValue({ ...POINTS_PLAN, id: "plan-new" });
    updateMutateAsync.mockResolvedValue(POINTS_PLAN);
    replaceMutateAsync.mockResolvedValue({
      plan_id: "plan-new",
      default_category_multiplier: 1,
      multipliers: {},
    });
    createMock.mockReturnValue({
      mutateAsync: createMutateAsync,
      isPending: false,
    } as unknown as ReturnType<typeof useCreatePlan>);
    updateMock.mockReturnValue({
      mutateAsync: updateMutateAsync,
      isPending: false,
    } as unknown as ReturnType<typeof useUpdatePlan>);
    replaceMock.mockReturnValue({
      mutateAsync: replaceMutateAsync,
      isPending: false,
    } as unknown as ReturnType<typeof useReplacePlanMultipliers>);
    multipliersMock.mockReturnValue({
      data: undefined,
      isLoading: false,
    } as unknown as ReturnType<typeof usePlanMultipliers>);
  });

  it("新增：預設 Token 制，點數欄位隱藏、用盡策略區塊仍顯示", () => {
    renderWithProviders(
      <PlanFormDialog plan={null} open={true} onOpenChange={vi.fn()} />,
    );
    expect(screen.getByRole("radio", { name: "Token 制" })).toBeChecked();
    expect(screen.queryByLabelText("每月基本點數")).not.toBeInTheDocument();
    expect(screen.getByRole("radio", { name: "自動展延" })).toBeChecked();
    expect(screen.getByRole("switch", { name: "租戶可自行切換" })).not.toBeChecked();
    expect(screen.getByLabelText("自動展延每月上限")).toHaveValue(0);
  });

  it("新增：切到點數制後顯示點數欄位與類別倍率表，存檔後以新方案 id 寫入倍率", async () => {
    const user = userEvent.setup();
    const onOpenChange = vi.fn();
    renderWithProviders(
      <PlanFormDialog plan={null} open={true} onOpenChange={onOpenChange} />,
    );

    await user.type(screen.getByLabelText("名稱 (英數識別碼，唯一)"), "starter-pts");
    await user.click(screen.getByRole("radio", { name: "點數制" }));

    const monthlyPoints = screen.getByLabelText("每月基本點數");
    await user.clear(monthlyPoints);
    await user.type(monthlyPoints, "3000");
    // 類別倍率：Web 對話設 0（不扣點）、RAG 設 1.5，其餘留空（沿用預設）
    await user.type(screen.getByLabelText("Web 對話"), "0");
    await user.type(screen.getByLabelText("RAG 查詢"), "1.5");

    await user.click(screen.getByRole("button", { name: "儲存" }));

    await waitFor(() => expect(createMutateAsync).toHaveBeenCalledTimes(1));
    expect(createMutateAsync.mock.calls[0][0]).toMatchObject({
      name: "starter-pts",
      billing_mode: "points",
      monthly_points: 3000,
      addon_pack_points: 0,
      default_category_multiplier: 1,
      exhaustion_policy: "auto_topup",
      tenant_may_change_policy: false,
      auto_topup_monthly_cap: 0,
      grace_percent: 0,
      block_message: "",
    });

    await waitFor(() => expect(replaceMutateAsync).toHaveBeenCalledTimes(1));
    expect(replaceMutateAsync.mock.calls[0][0]).toEqual({
      planId: "plan-new",
      data: { multipliers: { rag: 1.5, chat_web: 0 } },
    });
    expect(onOpenChange).toHaveBeenCalledWith(false);
  });

  it("新增：Token 制存檔不呼叫倍率端點，且帶出用盡策略欄位", async () => {
    const user = userEvent.setup();
    renderWithProviders(
      <PlanFormDialog plan={null} open={true} onOpenChange={vi.fn()} />,
    );

    await user.type(screen.getByLabelText("名稱 (英數識別碼，唯一)"), "basic");
    await user.click(screen.getByRole("radio", { name: "用完即擋" }));
    await user.click(screen.getByRole("switch", { name: "租戶可自行切換" }));
    const cap = screen.getByLabelText("自動展延每月上限");
    await user.clear(cap);
    await user.type(cap, "3");
    const grace = screen.getByLabelText("寬限百分比");
    await user.clear(grace);
    await user.type(grace, "10");
    await user.type(screen.getByLabelText("被擋文案"), "額度已用完");

    await user.click(screen.getByRole("button", { name: "儲存" }));

    await waitFor(() => expect(createMutateAsync).toHaveBeenCalledTimes(1));
    expect(createMutateAsync.mock.calls[0][0]).toMatchObject({
      billing_mode: "token",
      exhaustion_policy: "block",
      tenant_may_change_policy: true,
      auto_topup_monthly_cap: 3,
      grace_percent: 10,
      block_message: "額度已用完",
    });
    expect(replaceMutateAsync).not.toHaveBeenCalled();
  });

  it("編輯：點數制方案帶入既有欄位與倍率表，存檔以原 id 取代倍率", async () => {
    multipliersMock.mockReturnValue({
      // 後端 Decimal 可能序列化為字串
      data: { plan_id: "plan-pts", default_category_multiplier: "1", multipliers: { rag: "2" } },
      isLoading: false,
    } as unknown as ReturnType<typeof usePlanMultipliers>);
    const user = userEvent.setup();
    renderWithProviders(
      <PlanFormDialog plan={POINTS_PLAN} open={true} onOpenChange={vi.fn()} />,
    );

    expect(screen.getByRole("radio", { name: "點數制" })).toBeChecked();
    expect(screen.getByLabelText("每月基本點數")).toHaveValue(5000);
    expect(screen.getByLabelText("加購點數包")).toHaveValue(1000);
    expect(screen.getByRole("radio", { name: "用完即擋" })).toBeChecked();
    expect(screen.getByRole("switch", { name: "租戶可自行切換" })).toBeChecked();
    expect(screen.getByLabelText("被擋文案")).toHaveValue("額度用完");
    await waitFor(() => expect(screen.getByLabelText("RAG 查詢")).toHaveValue(2));

    await user.click(screen.getByRole("button", { name: "儲存" }));

    await waitFor(() => expect(updateMutateAsync).toHaveBeenCalledTimes(1));
    expect(updateMutateAsync.mock.calls[0][0]).toMatchObject({
      id: "plan-pts",
      data: { billing_mode: "points", monthly_points: 5000, exhaustion_policy: "block" },
    });
    await waitFor(() => expect(replaceMutateAsync).toHaveBeenCalledTimes(1));
    expect(replaceMutateAsync.mock.calls[0][0]).toEqual({
      planId: "plan-pts",
      data: { multipliers: { rag: 2 } },
    });
  });

  it("寬限百分比超過 100 時擋下送出", async () => {
    const user = userEvent.setup();
    renderWithProviders(
      <PlanFormDialog plan={null} open={true} onOpenChange={vi.fn()} />,
    );
    const grace = screen.getByLabelText("寬限百分比");
    await user.clear(grace);
    await user.type(grace, "150");
    await user.click(screen.getByRole("button", { name: "儲存" }));

    expect(screen.getByText("寬限百分比必須介於 0–100")).toBeInTheDocument();
    expect(createMutateAsync).not.toHaveBeenCalled();
  });
});
