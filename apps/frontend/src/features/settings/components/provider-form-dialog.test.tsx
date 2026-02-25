import { describe, expect, it } from "vitest";
import { screen } from "@testing-library/react";
import { renderWithProviders } from "@/test/test-utils";
import { ProviderFormDialog } from "./provider-form-dialog";

describe("ProviderFormDialog", () => {
  it("should render create form when no editing setting", () => {
    renderWithProviders(
      <ProviderFormDialog
        open={true}
        onOpenChange={() => {}}
        editingSetting={null}
      />,
    );

    expect(screen.getByText("新增供應商設定")).toBeInTheDocument();
    expect(screen.getByLabelText("顯示名稱")).toBeInTheDocument();
    expect(screen.getByLabelText(/API Key/)).toBeInTheDocument();
  });

  it("should render edit form when editing setting provided", () => {
    const setting = {
      id: "ps-001",
      provider_type: "llm" as const,
      provider_name: "openai",
      display_name: "OpenAI",
      is_enabled: true,
      has_api_key: true,
      base_url: "https://api.openai.com/v1",
      models: [],
      extra_config: {},
      created_at: "2026-01-01T00:00:00Z",
      updated_at: "2026-01-01T00:00:00Z",
    };

    renderWithProviders(
      <ProviderFormDialog
        open={true}
        onOpenChange={() => {}}
        editingSetting={setting}
      />,
    );

    expect(screen.getByText("編輯供應商設定")).toBeInTheDocument();
    expect(screen.getByLabelText("顯示名稱")).toHaveValue("OpenAI");
  });

  it("should have save and cancel buttons", () => {
    renderWithProviders(
      <ProviderFormDialog
        open={true}
        onOpenChange={() => {}}
        editingSetting={null}
      />,
    );

    expect(
      screen.getByRole("button", { name: "儲存" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "取消" }),
    ).toBeInTheDocument();
  });
});
