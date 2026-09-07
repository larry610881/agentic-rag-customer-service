import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import AdminGuardControlPage from "@/pages/admin-guard-control";
import { renderWithProviders } from "@/test/test-utils";
import type { GuardSettingsOverview, TenantGuardSettings } from "@/types/guard-stages";

vi.mock("@/hooks/queries/use-guard-stages", () => ({
  useGuardSettingsOverview: vi.fn(),
  useTenantGuardSettings: vi.fn(),
  useUpdateGuardPlatform: vi.fn(),
  useUpdateGuardProfile: vi.fn(),
  useUpdateGuardTenant: vi.fn(),
}));

vi.mock("@/hooks/queries/use-tenants", () => ({
  useTenants: vi.fn(() => ({
    data: {
      items: [
        { id: "t-1", name: "家樂福" },
        { id: "t-2", name: "康達盛通" },
      ],
      total: 2,
      page: 1,
      page_size: 100,
      total_pages: 1,
    },
    isLoading: false,
    isError: false,
  })),
}));

// Radix Select 在 jsdom 不可互動；租戶篩選以 mock 直接呈現原生 select
vi.mock("@/features/admin/components/admin-tenant-filter", () => ({
  AdminTenantFilter: ({
    value,
    onChange,
  }: {
    value?: string;
    onChange: (v?: string) => void;
  }) => (
    <select
      aria-label="租戶篩選"
      value={value ?? "all"}
      onChange={(e) => onChange(e.target.value === "all" ? undefined : e.target.value)}
    >
      <option value="all">全部租戶</option>
      <option value="t-1">家樂福</option>
      <option value="t-2">康達盛通</option>
    </select>
  ),
}));

import {
  useGuardSettingsOverview,
  useTenantGuardSettings,
  useUpdateGuardPlatform,
  useUpdateGuardProfile,
  useUpdateGuardTenant,
} from "@/hooks/queries/use-guard-stages";

const overviewMock = vi.mocked(useGuardSettingsOverview);
const tenantSettingsMock = vi.mocked(useTenantGuardSettings);
const platformMock = vi.mocked(useUpdateGuardPlatform);
const profileMock = vi.mocked(useUpdateGuardProfile);
const tenantMock = vi.mocked(useUpdateGuardTenant);

const platformMutate = vi.fn();
const profileMutate = vi.fn();
const tenantMutate = vi.fn();

const ALL_STAGES = [
  "regex_input",
  "classifier_attack",
  "output_guard",
  "abuse_scoring",
  "local_classifier",
];
const FLOOR = ["regex_input", "output_guard", "abuse_scoring"];

/** 平台未覆寫：底線 = 程式預設三段；預設啟用 = 三段 + 分類器 */
const OVERVIEW: GuardSettingsOverview = {
  platform_overrides: {},
  profiles: {
    standard: {},
    exhibition: { stages: ["regex_input", "output_guard", "abuse_scoring"] },
    strict: { stages: ["regex_input", "classifier_attack", "output_guard", "abuse_scoring"] },
  },
  effective_default: {
    stages: ["regex_input", "classifier_attack", "output_guard", "abuse_scoring"],
    required: FLOOR,
    locked: false,
    source_map: {
      regex_input: "required",
      classifier_attack: "platform",
      output_guard: "required",
      abuse_scoring: "required",
    },
    profile: "standard",
  },
  stages: ALL_STAGES,
  required_floor_default: FLOOR,
  builtin_profiles: ["exhibition", "standard"],
  allowed_keys: {
    platform: ["required_stages", "stages"],
    profile: ["stages"],
    tenant: ["locked", "profile", "stages"],
  },
};

const TENANTS: Record<string, TenantGuardSettings> = {
  // 展覽方案：分類器不在基底，租戶可加開
  "t-1": {
    tenant_id: "t-1",
    profile: "exhibition",
    overrides: { profile: "exhibition" },
    locked: false,
    effective: {
      stages: ["regex_input", "output_guard", "abuse_scoring"],
      required: FLOOR,
      locked: false,
      source_map: { regex_input: "required", output_guard: "required", abuse_scoring: "required" },
      profile: "exhibition",
    },
    editable: true,
  },
  // 未指定方案（standard）且已鎖定
  "t-2": {
    tenant_id: "t-2",
    profile: null,
    overrides: { locked: true },
    locked: true,
    effective: {
      stages: ["regex_input", "classifier_attack", "output_guard", "abuse_scoring"],
      required: FLOOR,
      locked: true,
      source_map: {
        regex_input: "required",
        classifier_attack: "platform",
        output_guard: "required",
        abuse_scoring: "required",
      },
      profile: "standard",
    },
    editable: true,
  },
};

function mockOverview(data: GuardSettingsOverview = OVERVIEW) {
  overviewMock.mockReturnValue({
    data,
    isLoading: false,
    isError: false,
  } as unknown as ReturnType<typeof useGuardSettingsOverview>);
}

describe("AdminGuardControlPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockOverview();
    tenantSettingsMock.mockImplementation(
      (tenantId) =>
        ({
          data: tenantId ? TENANTS[tenantId] : undefined,
          isLoading: false,
          isError: false,
        }) as unknown as ReturnType<typeof useTenantGuardSettings>,
    );
    platformMock.mockReturnValue({
      mutate: platformMutate,
      isPending: false,
    } as unknown as ReturnType<typeof useUpdateGuardPlatform>);
    profileMock.mockReturnValue({
      mutate: profileMutate,
      isPending: false,
    } as unknown as ReturnType<typeof useUpdateGuardProfile>);
    tenantMock.mockReturnValue({
      mutate: tenantMutate,
      isPending: false,
    } as unknown as ReturnType<typeof useUpdateGuardTenant>);
  });

  it("系統底線：未覆寫時以生效預設填入；必開階段的啟用鎖定；預留階段不可勾", () => {
    renderWithProviders(<AdminGuardControlPage />);
    expect(screen.getByRole("button", { name: "儲存系統底線" })).toBeDisabled();
    expect(screen.getByText("尚無變更")).toBeInTheDocument();

    for (const label of ["正則輸入防護", "輸出防護", "異常計分"]) {
      expect(screen.getByLabelText(`啟用 ${label}`)).toBeChecked();
      expect(screen.getByLabelText(`啟用 ${label}`)).toBeDisabled();
      expect(screen.getByLabelText(`必開 ${label}`)).toBeChecked();
    }
    expect(screen.getByLabelText("啟用 分類器攻擊判定")).toBeChecked();
    expect(screen.getByLabelText("必開 分類器攻擊判定")).not.toBeChecked();

    expect(screen.getByLabelText("啟用 地端小模型判定")).toBeDisabled();
    expect(screen.getByLabelText("必開 地端小模型判定")).toBeDisabled();
    expect(screen.getByText("即將推出")).toBeInTheDocument();
    expect(screen.getByText("成本：每題多一次小模型呼叫")).toBeInTheDocument();
  });

  it("系統底線：勾必開隱含啟用，payload 為 overrides {stages, required_stages}", async () => {
    const user = userEvent.setup();
    renderWithProviders(<AdminGuardControlPage />);

    const enabledClassifier = screen.getByLabelText("啟用 分類器攻擊判定");
    await user.click(enabledClassifier);
    expect(enabledClassifier).not.toBeChecked();
    await user.click(screen.getByLabelText("必開 分類器攻擊判定"));
    expect(enabledClassifier).toBeChecked();
    expect(enabledClassifier).toBeDisabled();

    await user.click(screen.getByRole("button", { name: "儲存系統底線" }));
    expect(platformMutate).toHaveBeenCalledTimes(1);
    expect(platformMutate.mock.calls[0][0]).toEqual({
      stages: ["regex_input", "classifier_attack", "output_guard", "abuse_scoring"],
      required_stages: ["regex_input", "classifier_attack", "output_guard", "abuse_scoring"],
    });
  });

  it("方案：內建標「內建」、自訂標「自訂」；沿用系統預設的方案以平台預設填入；底線不可取消", async () => {
    const user = userEvent.setup();
    renderWithProviders(<AdminGuardControlPage />);
    await user.click(screen.getByRole("tab", { name: "方案" }));

    const standard = screen.getByTestId("guard-profile-standard");
    expect(within(standard).getByText("內建")).toBeInTheDocument();
    expect(within(standard).getByText("沿用系統預設")).toBeInTheDocument();
    expect(within(standard).getByLabelText("分類器攻擊判定")).toBeChecked();
    expect(within(standard).getByLabelText("正則輸入防護")).toBeDisabled();
    expect(
      within(standard).queryByRole("button", { name: "還原為沿用系統預設" }),
    ).not.toBeInTheDocument();

    const exhibition = screen.getByTestId("guard-profile-exhibition");
    expect(within(exhibition).getByText("內建")).toBeInTheDocument();
    expect(within(exhibition).getByLabelText("分類器攻擊判定")).not.toBeChecked();

    const strict = screen.getByTestId("guard-profile-strict");
    expect(within(strict).getByText("自訂")).toBeInTheDocument();

    const saveBtn = within(exhibition).getByRole("button", { name: "儲存方案" });
    expect(saveBtn).toBeDisabled();
    await user.click(within(exhibition).getByLabelText("分類器攻擊判定"));
    await user.click(saveBtn);

    expect(profileMutate).toHaveBeenCalledTimes(1);
    expect(profileMutate.mock.calls[0][0]).toEqual({
      name: "exhibition",
      overrides: {
        stages: ["regex_input", "classifier_attack", "output_guard", "abuse_scoring"],
      },
    });
  });

  it("方案：自設清單的方案可還原為沿用系統預設（overrides 空物件）", async () => {
    const user = userEvent.setup();
    renderWithProviders(<AdminGuardControlPage />);
    await user.click(screen.getByRole("tab", { name: "方案" }));
    const strict = screen.getByTestId("guard-profile-strict");
    await user.click(within(strict).getByRole("button", { name: "還原為沿用系統預設" }));
    expect(profileMutate.mock.calls[0][0]).toEqual({ name: "strict", overrides: {} });
  });

  it("租戶：依租戶 id 讀取；基底不可取消並標示來源；加開只送加開項 + 鎖定", async () => {
    const user = userEvent.setup();
    renderWithProviders(<AdminGuardControlPage />);
    await user.click(screen.getByRole("tab", { name: "租戶" }));
    expect(screen.getByText("請選擇租戶以查看防護階段設定")).toBeInTheDocument();

    await user.selectOptions(screen.getByLabelText("租戶篩選"), "t-1");
    expect(tenantSettingsMock).toHaveBeenCalledWith("t-1");

    const regex = screen.getByLabelText("正則輸入防護");
    expect(regex).toBeChecked();
    expect(regex).toBeDisabled();
    expect(within(regex.closest("li")!).getByText("底線")).toBeInTheDocument();

    // 展覽方案：分類器不在基底 → 可加開
    const classifier = screen.getByLabelText("分類器攻擊判定");
    expect(classifier).not.toBeChecked();
    expect(classifier).toBeEnabled();

    const saveBtn = screen.getByRole("button", { name: "儲存租戶設定" });
    expect(saveBtn).toBeDisabled();

    await user.click(classifier);
    expect(within(classifier.closest("li")!).getByText("租戶啟用")).toBeInTheDocument();
    await user.click(screen.getByRole("switch", { name: "鎖定" }));
    await user.click(saveBtn);

    expect(tenantMutate).toHaveBeenCalledTimes(1);
    expect(tenantMutate.mock.calls[0][0]).toEqual({
      tenantId: "t-1",
      data: {
        profile: "exhibition",
        overrides: { stages: ["classifier_attack"] },
        locked: true,
      },
    });
  });

  it("租戶：未指定方案時視為 standard，系統預設的階段標示來源且不可取消", async () => {
    const user = userEvent.setup();
    renderWithProviders(<AdminGuardControlPage />);
    await user.click(screen.getByRole("tab", { name: "租戶" }));
    await user.selectOptions(screen.getByLabelText("租戶篩選"), "t-2");

    const classifier = screen.getByLabelText("分類器攻擊判定");
    expect(classifier).toBeChecked();
    expect(classifier).toBeDisabled();
    expect(within(classifier.closest("li")!).getByText("系統預設")).toBeInTheDocument();
    expect(screen.getByRole("switch", { name: "鎖定" })).toBeChecked();
    expect(screen.getByRole("button", { name: "儲存租戶設定" })).toBeDisabled();
  });

  it("有效預覽：以租戶清單逐列讀取有效階段、方案與鎖定", async () => {
    const user = userEvent.setup();
    renderWithProviders(<AdminGuardControlPage />);
    await user.click(screen.getByRole("tab", { name: "有效預覽" }));

    const carrefour = screen.getByRole("row", { name: /家樂福/ });
    expect(within(carrefour).getByText("exhibition")).toBeInTheDocument();
    expect(within(carrefour).getByTestId("effective-stage-regex_input")).toHaveTextContent(
      "正則輸入防護 · 底線",
    );
    expect(
      within(carrefour).queryByTestId("effective-stage-classifier_attack"),
    ).not.toBeInTheDocument();

    const kangda = screen.getByRole("row", { name: /康達盛通/ });
    expect(within(kangda).getByText("已鎖定")).toBeInTheDocument();
    expect(within(kangda).getByTestId("effective-stage-classifier_attack")).toHaveTextContent(
      "分類器攻擊判定 · 系統預設",
    );
  });

  it("載入失敗時顯示錯誤", () => {
    overviewMock.mockReturnValue({
      data: undefined,
      isLoading: false,
      isError: true,
    } as unknown as ReturnType<typeof useGuardSettingsOverview>);
    renderWithProviders(<AdminGuardControlPage />);
    expect(screen.getByText("無法載入設定")).toBeInTheDocument();
  });
});
