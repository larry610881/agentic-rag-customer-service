import { describe, it, expect, vi, beforeEach } from "vitest";
import { screen, waitFor } from "@testing-library/react";
import { renderWithProviders, userEvent } from "@/test/test-utils";
import { CreateApiKeyDialog } from "@/features/api-keys/components/create-api-key-dialog";
import type { ApiKeyCreated, CreateApiKeyRequest } from "@/types/api-key";

const createMutate = vi.fn();

vi.mock("@/hooks/queries/use-api-keys", () => ({
  useApiKeyScopes: () => ({
    data: ["chat:send", "chat:stream", "bots:read"],
    isLoading: false,
  }),
  useApiKeyBotOptions: () => ({
    data: [
      { id: "bot-1", name: "客服機器人" },
      { id: "bot-2", name: "行銷機器人" },
    ],
  }),
  useCreateApiKey: () => ({ mutate: createMutate, isPending: false }),
}));

const createdFixture: ApiKeyCreated = {
  id: "key-new",
  client_id: "key-new",
  client_secret: "sk_secret_ONLY_ONCE",
  tenant_id: "tenant-1",
  name: "官網整合",
  description: null,
  secret_prefix: "sk_secr",
  scopes: ["chat:send"],
  allowed_bot_ids: ["bot-1"],
  expires_at: null,
  revoked_at: null,
  is_active: true,
  last_used_at: null,
  created_by: null,
  created_at: "2026-09-03T00:00:00Z",
};

describe("CreateApiKeyDialog", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("validates that at least one scope is selected", async () => {
    const user = userEvent.setup();
    renderWithProviders(<CreateApiKeyDialog />);
    await user.click(screen.getByRole("button", { name: "建立金鑰" }));
    await user.type(screen.getByLabelText("名稱"), "官網整合");
    await user.click(screen.getByRole("button", { name: "建立" }));

    expect(screen.getByRole("alert")).toHaveTextContent("請至少選擇一個權限範圍");
    expect(createMutate).not.toHaveBeenCalled();
  });

  it("submits selected scopes, bots and tenant_id", async () => {
    const user = userEvent.setup();
    renderWithProviders(<CreateApiKeyDialog tenantId="tenant-1" />);
    await user.click(screen.getByRole("button", { name: "建立金鑰" }));
    await user.type(screen.getByLabelText("名稱"), "官網整合");
    await user.click(screen.getByLabelText(/chat:send/));
    await user.click(screen.getByLabelText(/bots:read/));
    await user.click(screen.getByLabelText("客服機器人"));
    await user.click(screen.getByRole("button", { name: "建立" }));

    expect(createMutate).toHaveBeenCalledTimes(1);
    const payload = createMutate.mock.calls[0][0] as CreateApiKeyRequest;
    expect(payload.name).toBe("官網整合");
    expect(payload.scopes).toEqual(["chat:send", "bots:read"]);
    expect(payload.allowed_bot_ids).toEqual(["bot-1"]);
    expect(payload.expires_at).toBeNull();
    expect(payload.tenant_id).toBe("tenant-1");
  });

  it("omits tenant_id for tenant_admin", async () => {
    const user = userEvent.setup();
    renderWithProviders(<CreateApiKeyDialog />);
    await user.click(screen.getByRole("button", { name: "建立金鑰" }));
    await user.type(screen.getByLabelText("名稱"), "x");
    await user.click(screen.getByLabelText(/chat:stream/));
    await user.click(screen.getByRole("button", { name: "建立" }));

    const payload = createMutate.mock.calls[0][0] as CreateApiKeyRequest;
    expect(payload).not.toHaveProperty("tenant_id");
  });

  it("shows the client_secret once after creation and hides it after closing", async () => {
    createMutate.mockImplementation(
      (_data: CreateApiKeyRequest, opts?: { onSuccess?: (d: ApiKeyCreated) => void }) => {
        opts?.onSuccess?.(createdFixture);
      },
    );
    const user = userEvent.setup();
    renderWithProviders(<CreateApiKeyDialog />);
    await user.click(screen.getByRole("button", { name: "建立金鑰" }));
    await user.type(screen.getByLabelText("名稱"), "官網整合");
    await user.click(screen.getByLabelText(/chat:send/));
    await user.click(screen.getByRole("button", { name: "建立" }));

    expect(screen.getByText("金鑰已建立")).toBeInTheDocument();
    expect(screen.getByLabelText("client_secret")).toHaveValue("sk_secret_ONLY_ONCE");
    expect(screen.getByLabelText("client_id")).toHaveValue("key-new");
    expect(screen.getByRole("alert")).toHaveTextContent("只會顯示這一次");
    expect(screen.getByRole("button", { name: "複製 client_secret" })).toBeInTheDocument();
    // curl 範例含 token 端點與 client_credentials
    expect(screen.getByText(/grant_type.*client_credentials/)).toBeInTheDocument();
    expect(screen.getByText(/\/api\/v1\/auth\/token/)).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "我已保存，關閉" }));
    await waitFor(() => {
      expect(screen.queryByText("金鑰已建立")).not.toBeInTheDocument();
    });

    // 重新開啟：回到空白表單，secret 不再出現
    await user.click(screen.getByRole("button", { name: "建立金鑰" }));
    expect(screen.getByText("建立 API 金鑰")).toBeInTheDocument();
    expect(screen.queryByText("sk_secret_ONLY_ONCE")).not.toBeInTheDocument();
  });
});
