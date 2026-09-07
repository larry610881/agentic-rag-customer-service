import { describe, expect, it } from "vitest";

import {
  GUARD_STAGE_DEFS,
  GUARD_STAGE_ORDER,
  describeGuardApiError,
  guardProfileDescription,
  guardSourceLabel,
  guardStageDefsFor,
  guardStageDef,
  guardStageLabel,
  sortGuardStages,
} from "@/features/guard-stages/guard-stage-labels";
import { ApiError } from "@/lib/api-client";

describe("guard-stage-labels", () => {
  it("五個階段依管線順序宣告，且 local_classifier 標為即將推出", () => {
    expect(GUARD_STAGE_ORDER).toEqual([
      "regex_input",
      "classifier_attack",
      "output_guard",
      "abuse_scoring",
      "local_classifier",
    ]);
    expect(guardStageDef("local_classifier")?.comingSoon).toBe(true);
    expect(GUARD_STAGE_DEFS.filter((d) => d.comingSoon)).toHaveLength(1);
  });

  it("中文標籤與成本提示", () => {
    expect(guardStageLabel("regex_input")).toBe("正則輸入防護");
    expect(guardStageLabel("classifier_attack")).toBe("分類器攻擊判定");
    expect(guardStageLabel("output_guard")).toBe("輸出防護");
    expect(guardStageLabel("abuse_scoring")).toBe("異常計分");
    expect(guardStageLabel("local_classifier")).toBe("地端小模型判定");
    expect(guardStageDef("classifier_attack")?.costHint).toBe("每題多一次小模型呼叫");
    expect(guardStageDef("regex_input")?.costHint).toBeUndefined();
    // 後端新增、前端尚未對照的階段直接回 key
    expect(guardStageLabel("future_stage")).toBe("future_stage");
  });

  it("來源標籤", () => {
    expect(guardSourceLabel("required")).toBe("底線");
    expect(guardSourceLabel("platform")).toBe("系統預設");
    expect(guardSourceLabel("profile")).toBe("方案");
    expect(guardSourceLabel("tenant")).toBe("租戶啟用");
    expect(guardSourceLabel("bot")).toBe("Bot 加嚴");
    expect(guardSourceLabel(undefined)).toBe("未啟用");
    expect(guardSourceLabel("fallback")).toBe("失效保護（全開）");
  });

  it("guardStageDefsFor 以後端全集為準，未知階段以 key 顯示，缺全集時退回前端宣告", () => {
    expect(guardStageDefsFor().map((d) => d.key)).toEqual(GUARD_STAGE_ORDER);
    const defs = guardStageDefsFor(["output_guard", "regex_input", "new_stage"]);
    expect(defs.map((d) => d.key)).toEqual(["regex_input", "output_guard", "new_stage"]);
    expect(defs[2].label).toBe("new_stage");
  });

  it("內建方案說明：standard 沿用、exhibition 不跑分類器；自訂依有無 stages", () => {
    expect(guardProfileDescription("standard")).toBe("沿用系統預設");
    expect(guardProfileDescription("exhibition")).toContain("不跑分類器");
    expect(guardProfileDescription("vip", { stages: ["regex_input"] })).toBe("自訂預設階段");
    expect(guardProfileDescription("vip", {})).toBe("沿用系統預設");
  });

  it("sortGuardStages 去重並依管線順序排序，未知階段排最後", () => {
    expect(
      sortGuardStages(["abuse_scoring", "zzz", "regex_input", "abuse_scoring", "aaa"]),
    ).toEqual(["regex_input", "abuse_scoring", "aaa", "zzz"]);
  });

  it("describeGuardApiError 取 422 detail、403 權限、其餘 fallback", () => {
    expect(describeGuardApiError(new ApiError(422, JSON.stringify({ detail: "底線不可關閉" })))).toBe(
      "底線不可關閉",
    );
    expect(describeGuardApiError(new ApiError(422, "not json"))).toBe(
      "設定驗證失敗，請檢查底線與階段清單",
    );
    expect(describeGuardApiError(new ApiError(403, ""))).toBe("沒有權限執行此操作");
    expect(describeGuardApiError(new Error("boom"), "自訂")).toBe("自訂");
  });
});
