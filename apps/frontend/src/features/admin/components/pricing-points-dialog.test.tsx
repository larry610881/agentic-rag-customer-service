import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { PricingPointsDialog } from "@/features/admin/components/pricing-points-dialog";
import { renderWithProviders } from "@/test/test-utils";
import type { ModelPricing } from "@/types/pricing";

vi.mock("@/hooks/queries/use-pricing", () => ({
  useUpdatePricingPoints: vi.fn(),
}));

import { useUpdatePricingPoints } from "@/hooks/queries/use-pricing";

const updateMock = vi.mocked(useUpdatePricingPoints);
const mutateAsync = vi.fn();

const PRICING: ModelPricing = {
  id: "pr-1",
  provider: "anthropic",
  model_id: "claude-haiku-4-5",
  display_name: "Claude Haiku 4.5",
  category: "llm",
  input_price: 1,
  output_price: 5,
  cache_read_price: 0.1,
  cache_creation_price: 1.25,
  effective_from: "2026-09-01T00:00:00Z",
  effective_to: null,
  created_by: "admin",
  created_at: "2026-09-01T00:00:00Z",
  note: "init",
  points_per_1k_input: 1,
  points_per_1k_output: 5,
};

describe("PricingPointsDialog（Issue #74）", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mutateAsync.mockResolvedValue(PRICING);
    updateMock.mockReturnValue({
      mutateAsync,
      isPending: false,
    } as unknown as ReturnType<typeof useUpdatePricingPoints>);
  });

  it("帶入既有點數並在修改後 PUT 兩欄", async () => {
    const user = userEvent.setup();
    const onOpenChange = vi.fn();
    renderWithProviders(
      <PricingPointsDialog pricing={PRICING} open={true} onOpenChange={onOpenChange} />,
    );
    const output = screen.getByLabelText("每千 token 輸出點數");
    expect(screen.getByLabelText("每千 token 輸入點數")).toHaveValue(1);
    expect(output).toHaveValue(5);

    await user.clear(output);
    await user.type(output, "6");
    await user.click(screen.getByRole("button", { name: "儲存點數" }));

    await waitFor(() => expect(mutateAsync).toHaveBeenCalledTimes(1));
    expect(mutateAsync.mock.calls[0][0]).toEqual({
      id: "pr-1",
      data: { points_per_1k_input: 1, points_per_1k_output: 6 },
    });
    expect(onOpenChange).toHaveBeenCalledWith(false);
  });

  it("兩欄同時清空 → PUT 兩欄 null（改用平台匯率）", async () => {
    const user = userEvent.setup();
    renderWithProviders(
      <PricingPointsDialog pricing={PRICING} open={true} onOpenChange={vi.fn()} />,
    );
    await user.clear(screen.getByLabelText("每千 token 輸入點數"));
    await user.clear(screen.getByLabelText("每千 token 輸出點數"));
    await user.click(screen.getByRole("button", { name: "儲存點數" }));

    await waitFor(() => expect(mutateAsync).toHaveBeenCalledTimes(1));
    expect(mutateAsync.mock.calls[0][0]).toEqual({
      id: "pr-1",
      data: { points_per_1k_input: null, points_per_1k_output: null },
    });
  });

  it("只清一欄時擋下送出", async () => {
    const user = userEvent.setup();
    renderWithProviders(
      <PricingPointsDialog pricing={PRICING} open={true} onOpenChange={vi.fn()} />,
    );
    await user.clear(screen.getByLabelText("每千 token 輸入點數"));
    await user.click(screen.getByRole("button", { name: "儲存點數" }));

    expect(screen.getByText(/需同時填寫，或同時留空/)).toBeInTheDocument();
    expect(mutateAsync).not.toHaveBeenCalled();
  });
});
