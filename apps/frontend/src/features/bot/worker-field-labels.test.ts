/** Issue #77 — Worker 欄位對照表與值格式器 */

import { describe, expect, it } from "vitest";

import {
  describeWorkerChange,
  formatWorkerFieldValue,
  workerFieldLabel,
} from "@/features/bot/worker-field-labels";

describe("workerFieldLabel", () => {
  it("maps worker fields to Chinese labels", () => {
    expect(workerFieldLabel("worker_prompt")).toBe("專屬提示詞");
    expect(workerFieldLabel("description")).toBe("路由描述");
    expect(workerFieldLabel("direct_retrieval")).toBe("快速道（直接檢索）");
    expect(workerFieldLabel("enabled_mcp_ids")).toBe("MCP 工具");
    expect(workerFieldLabel("llm_params.temperature")).toBe("溫度");
  });

  it("falls back to the raw key for unknown fields", () => {
    expect(workerFieldLabel("something_new")).toBe("something_new");
  });
});

describe("formatWorkerFieldValue", () => {
  it("reuses bot formatting for shared fields", () => {
    expect(formatWorkerFieldValue("direct_retrieval", true)).toBe("開");
    expect(formatWorkerFieldValue("knowledge_base_ids", ["kb-1", "kb-2"])).toBe("kb-1、kb-2");
    expect(formatWorkerFieldValue("knowledge_base_ids", [])).toBe("（空）");
    expect(formatWorkerFieldValue("temperature", 0.7)).toBe("0.7");
  });

  it("shows null enabled_tools as inherit-from-bot and [] as empty", () => {
    expect(formatWorkerFieldValue("enabled_tools", null)).toBe("繼承 Bot");
    expect(formatWorkerFieldValue("enabled_tools", [])).toBe("（空）");
  });

  it("shows empty llm_model as bot default", () => {
    expect(formatWorkerFieldValue("llm_model", null)).toBe("Bot 預設");
    expect(formatWorkerFieldValue("llm_model", "gpt-4o")).toBe("gpt-4o");
  });
});

describe("describeWorkerChange", () => {
  it("renders scalar changes and long-text deltas", () => {
    expect(
      describeWorkerChange({ field: "temperature", before: 0.3, after: 0.7 }),
    ).toBe("溫度：0.3 → 0.7");
    expect(
      describeWorkerChange({ field: "worker_prompt", before_len: 20, after_len: 140, changed: true }),
    ).toBe("專屬提示詞：已修改（+120 字）");
  });
});
