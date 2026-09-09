/** Issue #71 — Bot 欄位對照表與值格式器 */

import { describe, expect, it } from "vitest";

import {
  botFieldLabel,
  describeBotChange,
  describeLengthChange,
  diffBotValues,
  formatBotFieldValue,
} from "@/features/bot/bot-field-labels";

describe("botFieldLabel", () => {
  it("maps known keys and flattens llm_params.* to the leaf label", () => {
    expect(botFieldLabel("llm_model")).toBe("模型");
    expect(botFieldLabel("llm_params.temperature")).toBe("溫度");
    expect(botFieldLabel("bot_prompt")).toBe("Bot 自訂指令");
  });

  it("falls back to the raw key for unknown fields", () => {
    expect(botFieldLabel("something_new")).toBe("something_new");
  });
});

describe("formatBotFieldValue", () => {
  it("translates enum values", () => {
    expect(formatBotFieldValue("mode", "fast")).toBe("快速");
    expect(formatBotFieldValue("mode", "kb")).toBe("知識庫問答");
    expect(formatBotFieldValue("output_format", "plain_text")).toBe("純文字");
    expect(formatBotFieldValue("reasoning_effort", "none")).toBe("關閉");
    expect(formatBotFieldValue("llm_params.reasoning_effort", "high")).toBe("高");
    expect(formatBotFieldValue("gate_mode", "block")).toBe("阻擋");
  });

  it("renders booleans as 開/關 and is_active as 啟用/停用", () => {
    expect(formatBotFieldValue("rerank_enabled", true)).toBe("開");
    expect(formatBotFieldValue("rerank_enabled", false)).toBe("關");
    expect(formatBotFieldValue("is_active", false)).toBe("停用");
  });

  it("joins arrays and marks empties", () => {
    expect(formatBotFieldValue("enabled_tools", ["rag_query", "web"])).toBe(
      "rag_query、web",
    );
    expect(formatBotFieldValue("enabled_tools", [])).toBe("（空）");
    expect(formatBotFieldValue("llm_model", "")).toBe("（空）");
    expect(formatBotFieldValue("llm_model", null)).toBe("（空）");
  });

  it("never reveals secrets", () => {
    expect(formatBotFieldValue("line_channel_secret", "abc123")).toBe("••••••");
    expect(formatBotFieldValue("line_channel_secret", null)).toBe("（空）");
  });

  it("stringifies objects", () => {
    expect(formatBotFieldValue("output_schema", { type: "object" })).toBe(
      '{"type":"object"}',
    );
  });
});

describe("describeLengthChange", () => {
  it("reports + / − / unchanged", () => {
    expect(describeLengthChange(20, 140)).toBe("已修改（+120 字）");
    expect(describeLengthChange(140, 20)).toBe("已修改（−120 字）");
    expect(describeLengthChange(5, 5)).toBe("已修改（字數不變）");
  });
});

describe("describeBotChange", () => {
  it("renders scalar changes as label：before → after", () => {
    expect(
      describeBotChange({ field: "llm_model", before: "gpt-4o", after: "gemini-3.7-flash" }),
    ).toBe("模型：gpt-4o → gemini-3.7-flash");
    expect(
      describeBotChange({ field: "llm_params.temperature", before: 0.3, after: 0.7 }),
    ).toBe("溫度：0.3 → 0.7");
  });

  it("renders long text as a length delta for both diff and audit shapes", () => {
    expect(
      describeBotChange({ field: "bot_prompt", before: "x".repeat(20), after: "y".repeat(140) }),
    ).toBe("Bot 自訂指令：已修改（+120 字）");
    expect(
      describeBotChange({
        field: "memory_extraction_prompt",
        before_len: 100,
        after_len: 70,
        changed: true,
      }),
    ).toBe("記憶萃取提示詞：已修改（−30 字）");
  });
});

describe("diffBotValues", () => {
  const base = {
    name: "Bot",
    llm_model: "gpt-4o",
    temperature: 0.3,
    enabled_tools: ["rag_query"],
    summary_model: "",
    output_schema: null,
    tool_configs: {},
    line_channel_secret: null,
  };

  it("returns no diff when payload equals the baseline", () => {
    expect(diffBotValues(base, { ...base })).toEqual([]);
  });

  it("treats null / undefined / empty string / empty collections as equal", () => {
    expect(
      diffBotValues(base, {
        ...base,
        summary_model: undefined,
        output_schema: undefined,
        tool_configs: undefined,
        line_channel_secret: "",
      }),
    ).toEqual([]);
  });

  it("ignores fields absent from the payload", () => {
    expect(diffBotValues(base, { name: "Bot" })).toEqual([]);
  });

  it("detects scalar and array changes and orders them by the label table", () => {
    const diff = diffBotValues(base, {
      ...base,
      enabled_tools: ["rag_query", "web_search"],
      llm_model: "gemini-3.7-flash",
      temperature: 0.7,
    });
    expect(diff.map((d) => d.field)).toEqual(["llm_model", "temperature", "enabled_tools"]);
    expect(diff[0]).toEqual({ field: "llm_model", before: "gpt-4o", after: "gemini-3.7-flash" });
  });

  it("compares objects structurally regardless of key order", () => {
    expect(
      diffBotValues(
        { tool_configs: { rag_query: { rag_top_k: 3, rerank_enabled: true } } },
        { tool_configs: { rag_query: { rerank_enabled: true, rag_top_k: 3 } } },
      ),
    ).toEqual([]);
    expect(
      diffBotValues(
        { tool_configs: { rag_query: { rag_top_k: 3 } } },
        { tool_configs: { rag_query: { rag_top_k: 5 } } },
      ),
    ).toHaveLength(1);
  });
});
