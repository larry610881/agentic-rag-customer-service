import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeAll, describe, expect, it, vi } from "vitest";
import { ModelSelect } from "../model-select";
import type { EnabledModel } from "@/types/provider-setting";

// Issue #78：OCR 模型選單必須能選 google / openai 供應商（不只 anthropic）
const enabledModels: EnabledModel[] = [
  {
    provider_name: "google",
    model_id: "gemini-3.7-flash",
    display_name: "Gemini 3.7 Flash",
    price: "",
  },
  {
    provider_name: "anthropic",
    model_id: "claude-sonnet-4-6",
    display_name: "Claude Sonnet 4.6",
    price: "",
  },
  {
    provider_name: "openai",
    model_id: "gpt-5-mini",
    display_name: "GPT-5 mini",
    price: "",
  },
];

describe("ModelSelect", () => {
  beforeAll(() => {
    // jsdom 沒有 pointer capture（Radix Select 開啟時會呼叫）
    Element.prototype.hasPointerCapture ??= () => false;
    Element.prototype.releasePointerCapture ??= () => {};
  });

  it("依供應商分組列出 google / anthropic / openai 模型，值為 provider:model", async () => {
    const user = userEvent.setup();
    const onValueChange = vi.fn();
    render(
      <ModelSelect
        id="ocr-model"
        value=""
        onValueChange={onValueChange}
        enabledModels={enabledModels}
        allowEmpty
        emptyLabel="系統預設"
      />,
    );

    await user.click(screen.getByRole("combobox"));

    expect(await screen.findByText("Google Gemini")).toBeInTheDocument();
    expect(screen.getByText("Anthropic Claude")).toBeInTheDocument();
    expect(screen.getByText("OpenAI")).toBeInTheDocument();
    expect(screen.getByRole("option", { name: "系統預設" })).toBeInTheDocument();

    await user.click(screen.getByRole("option", { name: "Gemini 3.7 Flash" }));
    expect(onValueChange).toHaveBeenCalledWith("google:gemini-3.7-flash");
  });

  it("沒有啟用模型時顯示提示且不可選", async () => {
    const user = userEvent.setup();
    render(
      <ModelSelect value="" onValueChange={vi.fn()} enabledModels={[]} />,
    );
    await user.click(screen.getByRole("combobox"));
    expect(
      await screen.findByRole("option", { name: "尚未啟用任何模型" }),
    ).toHaveAttribute("aria-disabled", "true");
  });
});
