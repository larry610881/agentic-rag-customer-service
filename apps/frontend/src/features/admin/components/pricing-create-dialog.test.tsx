import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { PricingCreateDialog } from "@/features/admin/components/pricing-create-dialog";
import { renderWithProviders } from "@/test/test-utils";

vi.mock("@/hooks/queries/use-pricing", () => ({
  useCreatePricing: vi.fn(),
}));

import { useCreatePricing } from "@/hooks/queries/use-pricing";

const createMock = vi.mocked(useCreatePricing);
const mutateAsync = vi.fn();

async function fillRequired(user: ReturnType<typeof userEvent.setup>) {
  await user.type(screen.getByLabelText("Model ID"), "claude-haiku-4-5");
  await user.type(screen.getByLabelText("顯示名稱"), "Claude Haiku 4.5");
  await user.type(screen.getByLabelText(/改價理由/), "官方調價");
}

describe("PricingCreateDialog（Issue #74 點數欄位）", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mutateAsync.mockResolvedValue({});
    createMock.mockReturnValue({
      mutateAsync,
      isPending: false,
    } as unknown as ReturnType<typeof useCreatePricing>);
  });

  it("顯示兩個點數輸入與「留空則用平台匯率換算」提示", () => {
    renderWithProviders(<PricingCreateDialog open={true} onOpenChange={vi.fn()} />);
    expect(screen.getByLabelText("每千 token 輸入點數")).toBeInTheDocument();
    expect(screen.getByLabelText("每千 token 輸出點數")).toBeInTheDocument();
    expect(screen.getByText("留空則用平台匯率換算")).toBeInTheDocument();
  });

  it("點數留空 → payload 兩欄為 null", async () => {
    const user = userEvent.setup();
    renderWithProviders(<PricingCreateDialog open={true} onOpenChange={vi.fn()} />);
    await fillRequired(user);
    await user.click(screen.getByRole("button", { name: "建立新版本" }));

    await waitFor(() => expect(mutateAsync).toHaveBeenCalledTimes(1));
    expect(mutateAsync.mock.calls[0][0]).toMatchObject({
      model_id: "claude-haiku-4-5",
      points_per_1k_input: null,
      points_per_1k_output: null,
    });
  });

  it("填入點數 → payload 為數字", async () => {
    const user = userEvent.setup();
    renderWithProviders(<PricingCreateDialog open={true} onOpenChange={vi.fn()} />);
    await fillRequired(user);
    await user.type(screen.getByLabelText("每千 token 輸入點數"), "0.8");
    await user.type(screen.getByLabelText("每千 token 輸出點數"), "4");
    await user.click(screen.getByRole("button", { name: "建立新版本" }));

    await waitFor(() => expect(mutateAsync).toHaveBeenCalledTimes(1));
    expect(mutateAsync.mock.calls[0][0]).toMatchObject({
      points_per_1k_input: 0.8,
      points_per_1k_output: 4,
    });
  });

  it("只填一欄點數時擋下送出（後端兩欄需同時給值或同時 null）", async () => {
    const user = userEvent.setup();
    renderWithProviders(<PricingCreateDialog open={true} onOpenChange={vi.fn()} />);
    await fillRequired(user);
    await user.type(screen.getByLabelText("每千 token 輸入點數"), "0.8");
    await user.click(screen.getByRole("button", { name: "建立新版本" }));

    expect(screen.getByText(/需同時填寫，或同時留空/)).toBeInTheDocument();
    expect(mutateAsync).not.toHaveBeenCalled();
  });

  it("點數為負數時擋下送出", async () => {
    const user = userEvent.setup();
    renderWithProviders(<PricingCreateDialog open={true} onOpenChange={vi.fn()} />);
    await fillRequired(user);
    await user.type(screen.getByLabelText("每千 token 輸入點數"), "-1");
    await user.type(screen.getByLabelText("每千 token 輸出點數"), "1");
    await user.click(screen.getByRole("button", { name: "建立新版本" }));

    expect(screen.getByText(/每千 token 點數必須是 ≥ 0 的數字/)).toBeInTheDocument();
    expect(mutateAsync).not.toHaveBeenCalled();
  });
});
