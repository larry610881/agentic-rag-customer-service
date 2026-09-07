import { describe, expect, it } from "vitest";
import { ApiError } from "@/lib/api-client";
import {
  billingModeLabel,
  buildMultiplierPayload,
  describeBillingApiError,
  exhaustionPolicyLabel,
  formatMultiplier,
  formatPoints,
  formatTopupCap,
  formatUsdPerPoint,
  multipliersToForm,
  quotaExhaustedMessage,
  usedPercent,
} from "@/features/billing/billing-labels";

describe("billing-labels", () => {
  it("billingModeLabel：未知 / 空值回 Token 制或原字串", () => {
    expect(billingModeLabel("token")).toBe("Token 制");
    expect(billingModeLabel("points")).toBe("點數制");
    expect(billingModeLabel(undefined)).toBe("Token 制");
    expect(billingModeLabel("weird")).toBe("weird");
  });

  it("exhaustionPolicyLabel：空值顯示 —", () => {
    expect(exhaustionPolicyLabel("auto_topup")).toBe("自動展延");
    expect(exhaustionPolicyLabel("block")).toBe("用完即擋");
    expect(exhaustionPolicyLabel(null)).toBe("—");
  });

  it("formatPoints：整數千分位；空值 —", () => {
    expect(formatPoints(1234567)).toBe("1,234,567");
    expect(formatPoints(12.6)).toBe("13");
    expect(formatPoints(null)).toBe("—");
  });

  it("formatTopupCap：0 或空 = 不限", () => {
    expect(formatTopupCap(0)).toBe("不限");
    expect(formatTopupCap(undefined)).toBe("不限");
    expect(formatTopupCap(3)).toBe("3 次 / 月");
  });

  it("formatUsdPerPoint：小數位自適應", () => {
    expect(formatUsdPerPoint(0.001)).toBe("1 點 = 0.001000 USD");
    expect(formatUsdPerPoint(0.05)).toBe("1 點 = 0.0500 USD");
    expect(formatUsdPerPoint(2)).toBe("1 點 = 2.00 USD");
    expect(formatUsdPerPoint(undefined)).toBe("—");
  });

  it("formatMultiplier：整數不留小數、小數最多 3 位、空值為預設", () => {
    expect(formatMultiplier(1)).toBe("1×");
    expect(formatMultiplier(0.12345)).toBe("0.123×");
    expect(formatMultiplier(null)).toBe("預設");
  });

  it("usedPercent：total 為 0 回 0，超用封頂 100", () => {
    expect(usedPercent(50, 200)).toBe(25);
    expect(usedPercent(10, 0)).toBe(0);
    expect(usedPercent(300, 200)).toBe(100);
  });

  it("buildMultiplierPayload：空白略過（沿用預設）、0 保留、非數字回 error", () => {
    expect(buildMultiplierPayload({ rag: "", chat_web: "0", ocr: " 1.5 " })).toEqual({
      multipliers: { chat_web: 0, ocr: 1.5 },
      error: null,
    });
    expect(buildMultiplierPayload({ rag: "abc" }).error).toMatch(/rag/);
    expect(buildMultiplierPayload({ rag: "-1" }).error).toMatch(/rag/);
  });

  it("multipliersToForm：dict → 表單，未列出留空，Decimal 字串正規化", () => {
    expect(multipliersToForm({ rag: 2, ocr: "0.500" }, ["rag", "ocr", "guard"])).toEqual({
      rag: "2",
      ocr: "0.5",
      guard: "",
    });
    expect(multipliersToForm(undefined, ["rag"])).toEqual({ rag: "" });
  });

  it("quotaExhaustedMessage：402 quota_exhausted 取 message，其餘 null", () => {
    expect(
      quotaExhaustedMessage(
        new ApiError(402, JSON.stringify({ detail: "quota_exhausted", message: "額度用完了" })),
      ),
    ).toBe("額度用完了");
    expect(quotaExhaustedMessage(new ApiError(402, "not json"))).toBe(
      "本月額度已用完，服務暫停，請聯繫管理員。",
    );
    expect(quotaExhaustedMessage(new ApiError(403, JSON.stringify({ detail: "x" })))).toBeNull();
    expect(quotaExhaustedMessage(new Error("boom"))).toBeNull();
  });

  it("describeBillingApiError：403 為方案不允許、422 取 detail、其餘 fallback", () => {
    expect(describeBillingApiError(new ApiError(403, "Forbidden"))).toBe(
      "方案不允許租戶自行變更用盡策略",
    );
    expect(
      describeBillingApiError(new ApiError(422, JSON.stringify({ detail: "倍率超出範圍" }))),
    ).toBe("倍率超出範圍");
    expect(describeBillingApiError(new ApiError(422, "not json"))).toBe(
      "欄位驗證失敗，請檢查數值範圍",
    );
    expect(describeBillingApiError("boom", "儲存失敗")).toBe("儲存失敗");
  });
});
