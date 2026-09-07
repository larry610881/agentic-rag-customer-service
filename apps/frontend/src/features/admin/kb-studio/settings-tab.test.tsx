import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeAll, beforeEach, describe, expect, it, vi } from "vitest";
import { SettingsTab } from "./settings-tab";
import type { KnowledgeBase } from "@/types/knowledge";

vi.mock("@/hooks/queries/use-knowledge-bases", () => ({
  useKnowledgeBase: vi.fn(),
  useUpdateKnowledgeBase: vi.fn(),
}));
vi.mock("@/hooks/queries/use-provider-settings", () => ({
  useEnabledModels: vi.fn(),
}));

import {
  useKnowledgeBase,
  useUpdateKnowledgeBase,
} from "@/hooks/queries/use-knowledge-bases";
import { useEnabledModels } from "@/hooks/queries/use-provider-settings";

const mockedKb = vi.mocked(useKnowledgeBase);
const mockedUpdate = vi.mocked(useUpdateKnowledgeBase);
const mockedModels = vi.mocked(useEnabledModels);

const kb: KnowledgeBase = {
  id: "kb-1",
  tenant_id: "t-1",
  name: "家樂福 DM",
  description: "",
  ocr_mode: "catalog",
  ocr_model: "",
  context_model: "",
  classification_model: "",
  chunk_strategy: "separator",
  dm_metadata_model: "",
  document_count: 0,
  created_at: "2026-09-01T00:00:00Z",
  updated_at: "2026-09-01T00:00:00Z",
};

describe("SettingsTab — OCR 模型（Issue #78）", () => {
  beforeAll(() => {
    Element.prototype.hasPointerCapture ??= () => false;
    Element.prototype.releasePointerCapture ??= () => {};
  });

  beforeEach(() => {
    vi.clearAllMocks();
    mockedKb.mockReturnValue({
      data: kb,
      isLoading: false,
      error: null,
    } as unknown as ReturnType<typeof useKnowledgeBase>);
    mockedUpdate.mockReturnValue({
      mutate: vi.fn(),
      isPending: false,
    } as unknown as ReturnType<typeof useUpdateKnowledgeBase>);
    mockedModels.mockReturnValue({
      data: [
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
      ],
    } as unknown as ReturnType<typeof useEnabledModels>);
  });

  it("OCR 模型欄位顯示供應商提示", () => {
    render(<SettingsTab kbId="kb-1" />);
    expect(
      screen.getByText(/Gemini 3\.7 Flash 較省；Claude 4\.6 系列最穩/),
    ).toBeInTheDocument();
  });

  it("OCR 模型選單可選 google 供應商模型（值為 provider:model）", async () => {
    const user = userEvent.setup();
    render(<SettingsTab kbId="kb-1" />);

    const trigger = screen.getByRole("combobox", { name: "OCR 解析" });
    expect(trigger).toHaveTextContent("系統預設");
    await user.click(trigger);

    expect(await screen.findByText("Google Gemini")).toBeInTheDocument();
    await user.click(screen.getByRole("option", { name: "Gemini 3.7 Flash" }));
    expect(trigger).toHaveTextContent("Gemini 3.7 Flash");
  });
});
